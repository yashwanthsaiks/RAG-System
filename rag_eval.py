"""Evaluate the document-assistant RAG pipeline.

The scored path matches the server implementation:

- chunking via server/services/chunkingService.js (1000 characters, 200 overlap)
- embeddings with Ollama nomic-embed-text
- Chroma similarity search, top 4 chunks filtered by document id
- the prompt and llama3.2 settings in server/services/vectorDbService.js

Questions run against a labeled corpus in a separate Chroma collection
(rag_eval_embeddings). The production collection document_embeddings_ollama
is not modified. Ground truth is required for precision, recall, and the
confusion matrices; the uploaded resumes are not labeled.

Usage:
    python rag_eval.py
    python rag_eval.py --chunk-check
    python rag_eval.py --limit 2
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_DIR = ROOT / "server"
VECTOR_DB_PATH = SERVER_DIR / "services" / "vectorDbService.js"
REPORT_PATH = ROOT / "rag_eval_report.json"
EVAL_COLLECTION = "rag_eval_embeddings"
PROD_COLLECTION = "document_embeddings_ollama"
TOP_K = 4

ABSTAIN_PHRASES = (
    "does not contain",
    "doesn't contain",
    "doesnt contain",
    "do not contain",
    "not present in the context",
    "not in the context",
    "not in the provided context",
    "no information",
    "cannot find",
    "can't find",
    "cannot answer",
    "can't answer",
)


def _section(marker: str, text: str) -> dict:
    return {"marker": marker, "text": " ".join(text.split())}


DOCUMENTS = [
    {
        "id": "eval-harbor",
        "title": "Harbor workplace handbook",
        "sections": [
            _section(
                "10 business days",
                """
                Harbor employees must submit expense reports within 10 business days
                of the purchase. Reimbursements above 250 dollars require an itemized
                receipt attached to the report. Day-trip meals are capped at 60 dollars,
                and hotels must be booked through the Harbor travel desk. Cash advances
                are not issued for trips shorter than three nights. Receipt questions go
                to the finance mailbox expenses@harbor.example, and the review queue is
                checked every weekday afternoon. A manager may reject a report that has
                no business-purpose sentence. Foreign charges use the bank settlement
                rate from the purchase date. Personal subscriptions, ordinary commuting,
                and in-room movies are never reimbursed under this expense rule.
                """,
            ),
            _section(
                "Finance Director",
                """
                Any Harbor trip whose estimated total is over 1500 dollars must be
                approved by the Finance Director before tickets are bought. Flights
                shorter than six hours are booked as economy airfare, and first class
                is not used on domestic routes. Rail may replace a flight when the
                station-to-station time is under four hours. Hotel rooms are a standard
                single unless two employees share a twin room. Ride-hail trips after
                22:00 need a short safety note in the travel file. The travel calendar
                closes five business days before departure, and a later change needs a
                written exception from that same approver. Conference fees are paid
                only when the agenda is attached to the approval form.
                """,
            ),
            _section(
                "1.5 PTO days",
                """
                Full-time Harbor staff accrue 1.5 PTO days per month, credited on the
                first weekday of the following month. Unused PTO up to 10 days rolls
                over on January 1, and any balance above that cap is paid in the January
                payroll. New hires begin accruing on their 30th calendar day. A request
                of three or more consecutive days needs manager approval in the leave
                tool. Sick time is tracked separately and does not draw from the PTO
                balance. Employees on unpaid leave do not accrue during an unpaid month.
                The smallest request is one hour, and a partial day is entered before
                the shift starts. Approved time off appears on the team calendar within
                one business day, and a cancelled request returns the hours to the balance.
                """,
            ),
            _section(
                "America/Chicago",
                """
                Remote Harbor employees must be online from 10:00 to 15:00 in the
                America/Chicago timezone on scheduled workdays. Core collaboration
                happens in the Harbor channel, and cameras are expected for design
                reviews. An employee may work from another region for up to 10 calendar
                days if that midday window stays covered. The home-office stipend is
                paid once each March. An outage longer than 30 minutes is posted in the
                Harbor channel so meetings can move. Residential internet above the
                stipend is not reimbursed. Customer calls require a quiet room.
                Status is set to away during lunch so teammates know when to expect a reply. Managers review remote schedules every quarter and adjust coverage for public holidays.
                """,
            ),
            _section(
                "red lanyard",
                """
                Harbor identification badges come from the lobby security desk on the
                first morning. A lost badge is deactivated the same day, and a
                replacement costs 15 dollars on the next paycheck. Visitors never
                receive a staff badge. Tailgating at the turnstile is recorded and
                reviewed each Friday. Contractors wear a red lanyard and staff wear a
                blue lanyard. A badge that fails the reader twice goes back to the desk
                instead of being forced through the gate. After-hours entry needs the
                badge plus a personal pin that expires every 90 days.
                Badge photos are retaken every five years or after a major change in appearance. Security staff may ask anyone without a visible badge to return to the lobby desk.
                """,
            ),
            _section(
                "yellow sticker",
                """
                Harbor visitors sign in at the walnut lobby desk and wear a yellow
                sticker that is valid for that calendar day only. The host meets the
                visitor at the desk and escorts them above the second floor. Conference
                room Oak is the default room for external meetings. Photography in the
                lab corridor is not allowed. Deliveries go to the loading dock on the
                side street, not through the lobby. A visitor who arrives before 08:30
                waits in the chairs by the window. The office coordinator keeps the
                sign-in book for one year.
                Visitors leave the sticker in the tray by the exit when they go. Guests attending an evening event use a separate list that the host sends to the lobby desk a day ahead.
                """,
            ),
            _section(
                "Elm Street garage",
                """
                Harbor staff park in the Elm Street garage on levels two and three.
                Level one is kept for client visits and is not a daily commuting floor.
                The garage ticket is validated at the lobby desk before 18:00. Overnight
                parking is limited to on-call engineers and is noted on the facilities
                form. Motorcycles use the marked stalls beside the stairwell. Bicycles
                belong on the rack behind the dock, and unlocked bikes are left at the
                rider's own risk. The monthly staff garage rate is 40 dollars, taken
                from the first paycheck of the month.
                Electric vehicle chargers on level two are shared on a first come basis with a two hour limit. Lost garage tickets are replaced at the lobby desk for a small fee.
                """,
            ),
            _section(
                "fourth floor restocks",
                """
                The Harbor pantry on the fourth floor restocks tea, oats, and fruit on
                Monday and Thursday mornings. The last person to use the espresso
                machine after 16:00 cleans it. Personal food left in the refrigerator
                is discarded every Friday at noon. The pantry is not a meeting room,
                and laptop calls move to a phone booth. Allergens are listed on the
                cupboard card, and peanut snacks stay on the top shelf only. Cups go
                back to the dishwasher rack instead of the sink. Team lunch orders are
                placed with the office coordinator by 11:00.
                Birthday cakes are welcome on the long counter as long as the crumbs are cleared the same afternoon. Requests for new snacks go in the suggestion box beside the fridge.
                """,
            ),
        ],
    },
    {
        "id": "eval-northwind",
        "title": "Northwind benefits guide",
        "sections": [
            _section(
                "500 dollars per plan year",
                """
                The Northwind individual medical deductible is 500 dollars per plan
                year, and the family deductible is 1200 dollars. Preventive visits,
                including the annual checkup and routine vaccines, have a 0 dollar
                copay at an in-network clinic. Specialist visits have a 40 dollar copay
                after the deductible is met. Emergency room care has a separate copay
                that is waived if the patient is admitted. Out-of-network claims pay
                60 percent of the allowed amount. The plan year starts on July 1.
                Members send itemized bills to claims@northwind.example within 90 days
                of the visit.
                The plan card is mailed to the home address within two weeks of enrollment, and a digital copy is kept in the benefits portal.
                """,
            ),
            _section(
                "4 percent of base salary",
                """
                Northwind matches 401k contributions up to 4 percent of base salary,
                and the match is deposited with each payroll. Vesting of the company
                match finishes after 3 years of continuous service. Someone who leaves
                earlier keeps the employee contribution and forfeits the unvested match.
                The contribution percentage can change on the first day of any month.
                The default investment is the target-date fund closest to the employee's
                65th birthday. Only one loan against the plan may be active. Catch-up
                contributions follow the federal limit and are not matched above the
                stated cap. Statements post on the second Friday of each month.
                """,
            ),
            _section(
                "12 weeks of paid parental leave",
                """
                Primary caregivers at Northwind receive 12 weeks of paid parental leave,
                and secondary caregivers receive 4 weeks. Leave may start up to two
                weeks before the birth or placement date. The weeks need not be
                consecutive, but they are used within six months. Health coverage
                continues at the employee rate during the paid weeks. When the date is
                known, notice goes in the benefits portal at least 30 days ahead. The
                manager and employee write a short return-to-work plan in the final
                week. A holiday closure during the leave does not extend either allotment.
                Questions about pay during leave go to the benefits team rather than payroll. Adoption and foster placements qualify for the same allotments as a birth.
                """,
            ),
            _section(
                "two cleanings per plan year",
                """
                Northwind dental coverage pays for two cleanings per plan year at a 0
                dollar copay in network. Fillings are covered at 80 percent after a
                dental deductible that is separate from the medical deductible. Crowns
                are covered at 50 percent and need a pre-treatment estimate. Orthodontia
                is available only for enrolled children under 19 and has a lifetime
                maximum. Night guards are covered once every three years. In-network
                dentists file the claim. Out-of-network dentists are reimbursed from a
                mailed receipt.
                Dental enrollment is chosen during open enrollment and stays fixed for the plan year unless a qualifying life event occurs. Emergency dental visits follow the same network rules.
                """,
            ),
            _section(
                "one eye exam per plan year",
                """
                The Northwind vision benefit provides one eye exam per plan year with a
                10 dollar copay. Frames are reimbursed up to 150 dollars every two
                years, and single-vision lenses are covered in full in network. A
                contact-lens fitting replaces glasses for that cycle and is not added
                on top of them. Non-prescription sunglasses are not reimbursed.
                Employees order frames through the Northwind vision portal. A lost pair
                is not replaced before the two-year mark. Pediatric exams use the same
                copay as adult exams.
                Safety glasses for lab roles are ordered through facilities rather than the vision plan. Laser eye surgery is not covered, though a partner clinic offers a member discount.
                """,
            ),
            _section(
                "wellness stipend of 300 dollars",
                """
                Northwind offers a wellness stipend of 300 dollars per calendar year
                for a gym membership, fitness classes, or an approved race. The stipend
                does not cover supplements, clothing, or home equipment. Receipts go
                in the wellness form by December 15. A flu-shot clinic is held in the
                atrium each October at no cost. The meditation room on the second floor
                can be reserved in 30 minute blocks. Step challenges are optional and
                do not affect benefits eligibility. Coaching through the employee
                assistance line is available 24 hours a day.
                Stipend payments arrive with the next payroll after a receipt is approved. Part-time employees receive a prorated amount based on their scheduled hours.
                """,
            ),
            _section(
                "one year of base salary",
                """
                Northwind provides basic life insurance equal to one year of base salary
                at no premium to the employee. Supplemental life insurance can be bought
                in units up to four times salary, with evidence of insurability above
                two times salary. Beneficiary forms live in the benefits portal and
                should be reviewed after a marriage or a birth. Accidental death
                coverage matches the basic amount. The policy does not cover acts of
                war. Coverage reduces by half at age 70. Human resources starts a claim
                after a death certificate is provided.
                Spouses and children may be added to supplemental coverage during open enrollment. A conversion option lets a departing employee keep a personal policy without a new medical review.
                """,
            ),
            _section(
                "pre-tax payroll deduction",
                """
                Northwind commuter benefits allow a pre-tax payroll deduction for
                transit passes and a smaller election for qualified parking. The
                election can change on the first of the month. Unused transit funds
                roll for two months and then expire. Bicycle commuting is not part of
                this pre-tax account. Company vanpool seats are billed through the same
                election. Transit passes bought in the Northwind commuter portal do not
                need a separate receipt. Airport parking is not a qualified commuter
                expense.
                Employees who move offices update their commuter election in the portal before the new month begins. Ferry tickets count as transit when they are bought through the commuter portal. Rideshare trips do not qualify.
                """,
            ),
        ],
    },
    {
        "id": "eval-field",
        "title": "Field kit manual",
        "sections": [
            _section(
                "CR123A lithium battery",
                """
                The field radio uses a CR123A lithium battery, and the spare battery
                lives in pouch B of the pack lid. A fresh cell is expected to run the
                radio for 18 hours at a low transmit duty cycle. Radios are checked on
                channel 4 before leaving camp. The antenna is fully extended before a
                transmission, and the radio is stored powered off so the spare cell is
                not drained overnight. A wet cell is discarded rather than dried and
                reused. Call signs are written on the radio tag. A cracked case goes to
                the quartermaster and is not taped for reuse.
                Radio checks repeat every evening at the agreed time so missing teams are noticed early. Spare antennas are not carried, so a bent antenna is straightened gently and reported.
                """,
            ),
            _section(
                "weighs 1.8 kilograms",
                """
                The trail tent weighs 1.8 kilograms and sleeps 2 people. The poles are
                aluminum and the stakes are aluminum, stored in the side sleeve. The
                first pitch needs two people and later pitches need one. The footprint
                is packed under the tent body so it is not left at the site. Rainfly
                seams are sealed at the start of each season. Cooking inside the tent
                is not allowed. The stuff sack is red so it can be found in the pack.
                A torn mesh panel is patched before the next assignment.
                Guy lines are tensioned after the rainfly goes on and checked again before dark. The tent is aired out and fully dried at the base before it returns to storage, and a missing stake is logged on the gear sheet.
                """,
            ),
            _section(
                "2 liters per minute",
                """
                The field filter purifies 2 liters per minute from clear stream water.
                Replace the cartridge after 400 liters or when the flow becomes slow,
                whichever comes first. The intake hose is stored in a different bag
                from the clean bottle. Backflush the filter for several strokes after
                each day of use. Do not let the cartridge freeze, because ice cracks
                the element and the stated flow does not return. Silty water sits in a
                pot for ten minutes before filtering. The clean bottle is marked with
                a blue ring.
                A spare cartridge is carried on trips longer than a week. Water from glacial streams is left to settle longer because fine sediment clogs the element quickly. Filtered water is still boiled when the source is near grazing animals.
                """,
            ),
            _section(
                "canister fuel",
                """
                The field stove burns canister fuel and boils a small pot of water in
                about four minutes at low elevation. The canister is carried upright
                in an outer pocket, never inside the tent. A windscreen is required
                above the tree line. The stove is not used as a tent heater. The jet
                is cleaned with the wire stored in the knob. Spare rings sit in the
                repair tin. The stove cools before it is packed against the food bag.
                Empty canisters are packed out and are not left at the campsite.
                Each team carries enough fuel for one hot meal and two hot drinks per person per day. The stove is lit only on bare rock or gravel, and a full pot is never left unattended while the flame is on. Lighters are kept in a dry bag next to the matches.
                """,
            ),
            _section(
                "1 to 24000 scale",
                """
                Each team carries a paper topographic map at a 1 to 24000 scale even
                when a phone is available. The map stays in a zip bag in the top lid.
                Grid coordinates for the trailhead are written on the cover before
                departure. Route marks are made in pencil so they can be erased. The
                declination for the current year is noted in the margin. A lost map is
                reported on the radio so another team can share a spare. A digital
                track does not replace the paper sheet.
                Each member learns to take a bearing with the compass before the first field day. Teams compare their position on the map at every trail junction and note the time. The compass is stored away from the radio speaker magnet. Old maps are returned to the office at the end of the season.
                """,
            ),
            _section(
                "blister pads",
                """
                The first aid roll contains gauze, tape, blister pads, and a pair of
                nitrile gloves. The roll sits in the hip pocket so it can be reached
                without dropping the pack. Antihistamine tablets are in a labeled vial
                whose expiry is checked each March. Tourniquet use is limited to
                trained leads. Used gloves are packed out in a waste bag. The card in
                the roll lists the ranger station phone. Chemical cold packs are single
                use. The roll is restocked the same day the team returns.
                Every lead completes a wilderness first aid course before the season starts. Injuries are written in the incident log that evening, even when they seem minor. Water purification tablets are kept in the roll as a backup to the filter.
                """,
            ),
            _section(
                "wool base layer",
                """
                The clothing kit is a wool base layer, a wind shirt, and a rain shell.
                Cotton shirts are not issued because they dry slowly. The rain shell
                is packed at the top of the pack. Extra socks stay in a dry bag.
                Gaiters are issued only for scree routes. The team lead checks that
                each person has the shell before the truck leaves. Name tape goes on
                the collar. A soaked shell is hung in the cook area and is not laid on
                a sleeping bag.
                A warm hat and light gloves are packed even in summer because evenings above the tree line turn cold quickly. Sun hats have a wide brim. Damaged clothing is swapped at the quartermaster's office, and borrowed items are washed before they return to the shelf.
                """,
            ),
            _section(
                "ankle height with a firm lug sole",
                """
                Issued boots are ankle height with a firm lug sole. They are broken in
                on three short walks before a field day. Spare laces are taped inside
                the left boot. Hot spots are taped before the hike starts. Boots dry
                at room temperature, not beside the stove. The quartermaster replaces
                a sole when the lugs are worn smooth. Socks are wool and are changed
                at midday on wet trails. Boots do not go inside the tent.
                Trail runners are allowed only on maintained paths below the tree line. Boot sizes are recorded on the gear sheet so replacements can be ordered before the season. A boot with a separated toe cap is withdrawn from service right away. Insoles are aired out each night so they do not stay damp, and muddy boots are rinsed before they come back to the store.
                """,
            ),
        ],
    },
]


def _q(
    qid: str,
    document_id: str,
    question: str,
    answerable: bool,
    markers: list[str],
    aliases: list[str],
) -> dict:
    return {
        "id": qid,
        "document_id": document_id,
        "question": question,
        "answerable": answerable,
        "markers": markers,
        "aliases": aliases,
    }


QUESTIONS = [
    _q("h-expense", "eval-harbor", "How soon must a Harbor employee submit an expense report after a purchase?", True, ["10 business days"], ["10 business days"]),
    _q("h-travel", "eval-harbor", "Who must approve a Harbor trip that costs more than 1500 dollars?", True, ["Finance Director"], ["finance director"]),
    _q("h-pto", "eval-harbor", "How many PTO days does a full-time Harbor employee accrue each month?", True, ["1.5 PTO days"], ["1.5 pto days", "1.5 days"]),
    _q("h-remote", "eval-harbor", "Which timezone covers the required online hours for remote Harbor employees?", True, ["America/Chicago"], ["america/chicago", "chicago"]),
    _q("n-deductible", "eval-northwind", "What is the Northwind individual medical deductible?", True, ["500 dollars per plan year"], ["500 dollars", "$500"]),
    _q("n-401k", "eval-northwind", "What percentage of base salary does the Northwind 401k match cover?", True, ["4 percent of base salary"], ["4 percent", "4%"]),
    _q("n-parental", "eval-northwind", "How many weeks of paid parental leave does a primary caregiver receive at Northwind?", True, ["12 weeks of paid parental leave"], ["12 weeks"]),
    _q("f-radio", "eval-field", "What battery does the field radio use?", True, ["CR123A lithium battery"], ["cr123a"]),
    _q("f-tent", "eval-field", "How much does the trail tent weigh?", True, ["weighs 1.8 kilograms"], ["1.8 kilograms", "1.8 kg"]),
    _q("f-filter", "eval-field", "How fast does the field water filter purify water?", True, ["2 liters per minute"], ["2 liters per minute", "2 litres per minute"]),
    _q("h-deductible-miss", "eval-harbor", "What is the individual medical deductible?", False, [], ["500 dollars", "$500"]),
    _q("h-battery-miss", "eval-harbor", "What battery does the field radio use?", False, [], ["cr123a"]),
    _q("n-pto-miss", "eval-northwind", "How many PTO days accrue each month?", False, [], ["1.5 pto days", "1.5 days"]),
    _q("n-tent-miss", "eval-northwind", "How much does the trail tent weigh?", False, [], ["1.8 kilograms", "1.8 kg"]),
    _q("f-401k-miss", "eval-field", "What percentage of salary does the 401k match cover?", False, [], ["4 percent", "4%"]),
    _q("f-travel-miss", "eval-field", "Who approves a trip that costs more than 1500 dollars?", False, [], ["finance director"]),
]


WORKER_JS = r"""
const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { performance } = require("perf_hooks");

require("dotenv").config({ path: path.join(__dirname, ".env"), quiet: true });

const { OllamaEmbeddings, ChatOllama } = require("@langchain/ollama");
const { CloudClient } = require("chromadb");
const { createTextChunks } = require("./services/chunkingService");

const EVAL_COLLECTION = "rag_eval_embeddings";
const PROD_COLLECTION = "document_embeddings_ollama";
if (EVAL_COLLECTION === PROD_COLLECTION) {
  throw new Error("refusing to modify the production collection");
}

const vectorSource = fs.readFileSync(
  path.join(__dirname, "services", "vectorDbService.js"),
  "utf8"
);
const promptStart = vectorSource.indexOf("const prompt = `");
if (promptStart < 0) throw new Error("RAG prompt template was not found");
const promptBodyStart = promptStart + "const prompt = `".length;
const promptEnd = vectorSource.indexOf("`;", promptBodyStart);
if (promptEnd < 0) throw new Error("RAG prompt template did not end");
const promptTemplate = vectorSource.slice(promptBodyStart, promptEnd);

const topKMarker = "topK = ";
const topKAt = vectorSource.indexOf(topKMarker);
const TOP_K = topKAt < 0 ? 4 : Number(vectorSource.slice(topKAt + topKMarker.length, topKAt + topKMarker.length + 1));

const OLLAMA_HOST = process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434";
const embeddingsModel = new OllamaEmbeddings({
  model: "nomic-embed-text",
  baseUrl: OLLAMA_HOST,
});
const llmModel = new ChatOllama({
  model: "llama3.2",
  baseUrl: OLLAMA_HOST,
  temperature: 0.2,
  clientOptions: { timeout: 300000 },
});
const chromaClient = new CloudClient({
  apiKey: process.env.CHROMA_API_KEY,
  tenant: process.env.CHROMA_TENANT,
  database: process.env.CHROMA_DATABASE,
});
const dummyEmbeddingFunction = { generate: async () => [] };

function reply(payload) {
  process.stdout.write(JSON.stringify(payload) + "\n");
}

function buildPrompt(context, queryText) {
  return promptTemplate.split("${context}").join(context).split("${queryText}").join(queryText);
}

function nsToMs(value) {
  return typeof value === "number" ? Math.round((value / 1e6) * 10) / 10 : null;
}

async function deleteEvalCollection() {
  try {
    await chromaClient.deleteCollection({ name: EVAL_COLLECTION });
  } catch (error) {
    const message = String((error && error.message) || error);
    const name = String((error && error.name) || "");
    if (!/NotFound/.test(name) && !/not (be )?found|does not exist|404/i.test(message)) throw error;
  }
}

async function openCollection() {
  return chromaClient.getOrCreateCollection({
    name: EVAL_COLLECTION,
    embeddingFunction: dummyEmbeddingFunction,
  });
}

async function handle(msg) {
  if (msg.op === "chunk") {
    const docs = await createTextChunks(msg.text);
    return { chunks: docs.map((doc) => doc.pageContent) };
  }

  if (msg.op === "reset") {
    await deleteEvalCollection();
    await openCollection();
    return { collection: EVAL_COLLECTION };
  }

  if (msg.op === "index") {
    const collection = await openCollection();
    const docs = await createTextChunks(msg.text);
    const ids = [];
    const embeddings = [];
    const documents = [];
    const metadatas = [];
    const embedStarted = performance.now();
    for (let i = 0; i < docs.length; i += 1) {
      const chunkText = docs[i].pageContent;
      const vector = await embeddingsModel.embedQuery(chunkText);
      ids.push(`${msg.documentId}-chunk-${i}`);
      embeddings.push(vector);
      documents.push(chunkText);
      metadatas.push({ documentId: String(msg.documentId), chunkIndex: i });
    }
    await collection.add({ ids, embeddings, documents, metadatas });
    return {
      embed_ms: Math.round((performance.now() - embedStarted) * 10) / 10,
      chunks: ids.map((id, i) => ({
        id,
        text: documents[i],
        chunkIndex: i,
      })),
    };
  }

  if (msg.op === "warmup") {
    const started = performance.now();
    const response = await llmModel.invoke("Reply with the single word ready.");
    return {
      warmup_ms: Math.round((performance.now() - started) * 10) / 10,
      reply: typeof response.content === "string" ? response.content : "",
    };
  }

  if (msg.op === "query") {
    const collection = await openCollection();
    const embedStarted = performance.now();
    const queryVector = await embeddingsModel.embedQuery(msg.question);
    const embedMs = Math.round((performance.now() - embedStarted) * 10) / 10;

    const retrievalStarted = performance.now();
    const queryResults = await collection.query({
      queryEmbeddings: [queryVector],
      nResults: TOP_K,
      where: { documentId: String(msg.documentId) },
    });
    const retrievalMs = Math.round((performance.now() - retrievalStarted) * 10) / 10;

    const matchedTexts = (queryResults.documents && queryResults.documents[0]) || [];
    const matchedIds = (queryResults.ids && queryResults.ids[0]) || [];
    const distances = (queryResults.distances && queryResults.distances[0]) || [];
    const context = matchedTexts.join("\n\n---\n\n");
    const prompt = buildPrompt(context, msg.question);

    const llmStarted = performance.now();
    const response = await llmModel.invoke(prompt);
    const llmWallMs = Math.round((performance.now() - llmStarted) * 10) / 10;
    const metadata = response.response_metadata || {};
    const content = typeof response.content === "string" ? response.content : JSON.stringify(response.content);

    return {
      top_k: TOP_K,
      answer: content,
      ids: matchedIds,
      sources: matchedTexts,
      distances,
      embed_ms: embedMs,
      retrieval_ms: retrievalMs,
      llm_wall_ms: llmWallMs,
      llm_load_ms: nsToMs(metadata.load_duration),
      llm_prompt_ms: nsToMs(metadata.prompt_eval_duration),
      llm_generation_ms: nsToMs(metadata.eval_duration),
      llm_total_ms: nsToMs(metadata.total_duration),
      prompt_tokens: metadata.prompt_eval_count ?? null,
      completion_tokens: metadata.eval_count ?? null,
    };
  }

  if (msg.op === "cleanup") {
    await deleteEvalCollection();
    return { deleted: EVAL_COLLECTION };
  }

  throw new Error(`Unknown op ${msg.op}`);
}

async function main() {
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  for await (const line of rl) {
    if (!line.trim()) continue;
    let msg;
    try {
      msg = JSON.parse(line);
      const result = await handle(msg);
      reply({ ok: true, ...result });
    } catch (error) {
      reply({ ok: false, error: String((error && error.stack) || error) });
    }
  }
}

main().catch((error) => {
  reply({ ok: false, error: String((error && error.stack) || error) });
  process.exit(1);
});
"""


class Worker:
    def __init__(self, script_path: Path):
        self.script_path = script_path
        self.logs: list[str] = []
        self.proc = subprocess.Popen(
            ["node", str(script_path)],
            cwd=str(SERVER_DIR),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

    def _drain_stderr(self) -> None:
        assert self.proc.stderr is not None
        for line in self.proc.stderr:
            self.logs.append(line)
            print(line, end="", flush=True)

    def request(self, payload: dict) -> dict:
        if self.proc.poll() is not None:
            raise RuntimeError(
                "RAG worker exited early.\n" + "".join(self.logs[-40:])
            )
        assert self.proc.stdin is not None
        assert self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError(
                    "RAG worker closed stdout.\n" + "".join(self.logs[-40:])
                )
            if line.lstrip().startswith("{"):
                break
            # Libraries sometimes log to stdout; show it but keep reading.
            print(line, end="", flush=True)
        data = json.loads(line)
        if not data.get("ok"):
            raise RuntimeError(data.get("error") or "RAG worker failed")
        return data

    def close(self) -> None:
        if self.proc.poll() is None and self.proc.stdin is not None:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)


def build_documents() -> list[dict]:
    documents = []
    seen_markers: dict[str, str] = {}
    for document in DOCUMENTS:
        parts = []
        sections = []
        for index, section in enumerate(document["sections"]):
            text = section["text"]
            marker = section["marker"]
            if marker not in text:
                raise SystemExit(f"{document['id']} section {index} is missing its marker")
            if marker in seen_markers:
                raise SystemExit(f"Marker {marker!r} is reused")
            seen_markers[marker] = document["id"]
            if len(text) < 620 or len(text) > 980:
                raise SystemExit(
                    f"{document['id']} section {index} length {len(text)} is outside 620-980"
                )
            sections.append({"id": f"{document['id']}-{index}", "marker": marker, "text": text})
            parts.append(text)
        full_text = "\n\n".join(parts)
        for marker, owner in seen_markers.items():
            if owner == document["id"] and full_text.count(marker) != 1:
                raise SystemExit(f"{marker!r} appears {full_text.count(marker)} times in {document['id']}")
        documents.append(
            {
                "id": document["id"],
                "title": document["title"],
                "sections": sections,
                "text": full_text,
            }
        )
    return documents


def assert_pipeline_contract() -> None:
    source = VECTOR_DB_PATH.read_text(encoding="utf-8")
    chunking = (SERVER_DIR / "services" / "chunkingService.js").read_text(encoding="utf-8")
    required = {
        VECTOR_DB_PATH.name: [
            "model: 'nomic-embed-text'",
            "model: 'llama3.2'",
            "temperature: 0.2",
            "topK = 4",
            "document_embeddings_ollama",
            'The document does not contain this information.',
        ],
        "chunkingService.js": ["chunkSize = 1000", "chunkOverlap = 200"],
    }
    missing = [item for item in required[VECTOR_DB_PATH.name] if item not in source]
    missing.extend(item for item in required["chunkingService.js"] if item not in chunking)
    if missing:
        raise SystemExit(
            "The RAG pipeline source changed. Update rag_eval.py before scoring: "
            + ", ".join(missing)
        )


def contains_any(text: str, aliases: list[str]) -> bool:
    haystack = text.casefold()
    return any(alias.casefold() in haystack for alias in aliases)


def is_abstention(answer: str) -> bool:
    haystack = answer.casefold()
    return any(phrase in haystack for phrase in ABSTAIN_PHRASES)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def summarize_latency(values: list[float]) -> dict | None:
    if not values:
        return None
    return {
        "count": len(values),
        "mean_ms": round(sum(values) / len(values), 1),
        "p50_ms": round(percentile(values, 0.50) or 0, 1),
        "p95_ms": round(percentile(values, 0.95) or 0, 1),
        "min_ms": round(min(values), 1),
        "max_ms": round(max(values), 1),
    }


def new_cm() -> dict:
    return {"tp": 0, "fp": 0, "fn": 0, "tn": 0}


def rates(cm: dict) -> dict:
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else None
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else None
    f1 = None
    if precision is not None and recall is not None and precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    total = sum(cm.values())
    accuracy = (cm["tp"] + cm["tn"]) / total if total else None
    return {
        "precision": None if precision is None else round(precision, 4),
        "recall": None if recall is None else round(recall, 4),
        "f1": None if f1 is None else round(f1, 4),
        "accuracy": None if accuracy is None else round(accuracy, 4),
        "support": total,
    }


def add_pair(cm: dict, gold: bool, predicted: bool) -> None:
    if gold and predicted:
        cm["tp"] += 1
    elif predicted:
        cm["fp"] += 1
    elif gold:
        cm["fn"] += 1
    else:
        cm["tn"] += 1


def add_retrieval(cm: dict, retrieved: set[str], gold: set[str], universe: set[str]) -> dict:
    tp = retrieved & gold
    fp = retrieved - gold
    fn = gold - retrieved
    tn = universe - retrieved - gold
    cm["tp"] += len(tp)
    cm["fp"] += len(fp)
    cm["fn"] += len(fn)
    cm["tn"] += len(tn)
    precision = len(tp) / len(retrieved) if retrieved else None
    recall = len(tp) / len(gold) if gold else None
    return {
        "tp": len(tp),
        "fp": len(fp),
        "fn": len(fn),
        "tn": len(tn),
        "precision": precision,
        "recall": recall,
    }


def assert_chunks(document: dict, chunks: list[str]) -> None:
    if len(chunks) != len(document["sections"]):
        preview = [
            {
                "length": len(chunk),
                "markers": [section["marker"] for section in document["sections"] if section["marker"] in chunk],
                "preview": chunk[:80],
            }
            for chunk in chunks
        ]
        raise SystemExit(
            f"{document['id']} produced {len(chunks)} chunks for {len(document['sections'])} sections:\n"
            + json.dumps(preview, indent=2)
        )
    for chunk in chunks:
        hits = [section["marker"] for section in document["sections"] if section["marker"] in chunk]
        if len(hits) != 1:
            raise SystemExit(f"{document['id']} chunk matched {hits or 'no markers'}")


def gold_ids(chunks: list[dict], markers: list[str]) -> list[str]:
    return [chunk["id"] for chunk in chunks if any(marker in chunk["text"] for marker in markers)]


def fmt_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def print_matrix(title: str, cm: dict, positive: str, negative: str) -> None:
    scored = rates(cm)
    print(f"\n{title}")
    print(f"  precision {fmt_rate(scored['precision'])}   recall {fmt_rate(scored['recall'])}   f1 {fmt_rate(scored['f1'])}")
    label_w = max(len(positive), len(negative), 12)
    print(f"  {'':<{label_w}}  pred {positive:<{label_w}}  pred {negative}")
    print(f"  gold {positive:<{label_w - 5}}  {cm['tp']:<{label_w + 5}}  {cm['fn']}")
    print(f"  gold {negative:<{label_w - 5}}  {cm['fp']:<{label_w + 5}}  {cm['tn']}")


def print_latency(title: str, summary: dict | None) -> None:
    print(f"\n{title}")
    if not summary:
        print("  not reported by the model response")
        return
    print(
        f"  mean {summary['mean_ms']:.1f} ms   p50 {summary['p50_ms']:.1f} ms   "
        f"p95 {summary['p95_ms']:.1f} ms   min {summary['min_ms']:.1f} ms   max {summary['max_ms']:.1f} ms"
    )


def mean_defined(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def run(chunk_check: bool, limit: int) -> dict:
    assert_pipeline_contract()
    documents = build_documents()
    questions = QUESTIONS if limit <= 0 else QUESTIONS[:limit]
    by_id = {document["id"]: document for document in documents}

    fd, worker_name = tempfile.mkstemp(prefix="_rag_eval_worker_", suffix=".js", dir=SERVER_DIR)
    os.close(fd)
    worker_path = Path(worker_name)
    worker_path.write_text(WORKER_JS, encoding="utf-8")
    worker = Worker(worker_path)
    try:
        for document in documents:
            chunked = worker.request({"op": "chunk", "text": document["text"]})
            assert_chunks(document, chunked["chunks"])
            print(f"Chunked {document['id']}: {len(chunked['chunks'])} chunks", flush=True)
        if chunk_check:
            return {"chunk_check": True, "documents": [{"id": doc["id"], "chunks": len(doc["sections"])} for doc in documents]}

        print("Creating the eval collection and indexing labeled documents...", flush=True)
        worker.request({"op": "reset"})
        indexed = {}
        index_embed_ms = 0.0
        for document in documents:
            result = worker.request(
                {"op": "index", "documentId": document["id"], "text": document["text"]}
            )
            assert_chunks(document, [chunk["text"] for chunk in result["chunks"]])
            indexed[document["id"]] = result["chunks"]
            index_embed_ms += result["embed_ms"]
            print(
                f"Indexed {document['id']}: {len(result['chunks'])} chunks in {result['embed_ms']:.0f} ms",
                flush=True,
            )

        print("Warming llama3.2 so question latency excludes model load...", flush=True)
        warmup = worker.request({"op": "warmup"})
        print(f"Warmup finished in {warmup['warmup_ms']:.0f} ms", flush=True)

        retrieval_cm = new_cm()
        end_to_end_cm = new_cm()
        abstain_cm = new_cm()
        cases = []
        reciprocal_ranks = []

        for number, question in enumerate(questions, start=1):
            result = worker.request(
                {
                    "op": "query",
                    "documentId": question["document_id"],
                    "question": question["question"],
                }
            )
            chunks = indexed[question["document_id"]]
            universe = {chunk["id"] for chunk in chunks}
            relevant = set(gold_ids(chunks, question["markers"]))
            retrieved_ids = list(result["ids"])
            retrieved = set(retrieved_ids)
            chunk_scores = add_retrieval(retrieval_cm, retrieved, relevant, universe) if question["answerable"] else None

            rank = None
            for position, chunk_id in enumerate(retrieved_ids, start=1):
                if chunk_id in relevant:
                    rank = position
                    break
            if question["answerable"]:
                reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)

            answer = result["answer"] or ""
            abstained = is_abstention(answer)
            fact_present = contains_any(answer, question["aliases"]) if question["aliases"] else False
            if question["answerable"]:
                predicted_success = (not abstained) and fact_present
            else:
                predicted_success = (not abstained) or fact_present
            add_pair(end_to_end_cm, question["answerable"], predicted_success)
            add_pair(abstain_cm, question["answerable"], not abstained)

            case = {
                "id": question["id"],
                "document_id": question["document_id"],
                "question": question["question"],
                "answerable": question["answerable"],
                "gold_chunk_ids": sorted(relevant),
                "retrieved_ids": retrieved_ids,
                "distances": [round(distance, 4) if isinstance(distance, (int, float)) else distance for distance in result["distances"]],
                "rank_of_gold": rank,
                "retrieval_precision": None if not chunk_scores or chunk_scores["precision"] is None else round(chunk_scores["precision"], 4),
                "retrieval_recall": None if not chunk_scores or chunk_scores["recall"] is None else round(chunk_scores["recall"], 4),
                "abstained": abstained,
                "fact_present": fact_present,
                "end_to_end_correct": predicted_success == question["answerable"],
                "answer": answer,
                "embed_ms": result["embed_ms"],
                "retrieval_ms": result["retrieval_ms"],
                "llm_wall_ms": result["llm_wall_ms"],
                "llm_load_ms": result["llm_load_ms"],
                "llm_prompt_ms": result["llm_prompt_ms"],
                "llm_generation_ms": result["llm_generation_ms"],
                "llm_total_ms": result["llm_total_ms"],
                "prompt_tokens": result["prompt_tokens"],
                "completion_tokens": result["completion_tokens"],
            }
            cases.append(case)
            print(
                f"[{number}/{len(questions)}] {question['id']} "
                f"hit={rank is not None if question['answerable'] else 'n/a'} "
                f"abstain={abstained} fact={fact_present} "
                f"llm={result['llm_wall_ms']:.0f} ms",
                flush=True,
            )

        answerable_cases = [case for case in cases if case["answerable"]]
        macro_precision = mean_defined([case["retrieval_precision"] for case in answerable_cases])
        macro_recall = mean_defined([case["retrieval_recall"] for case in answerable_cases])
        hit_rate = (
            sum(1 for case in answerable_cases if case["rank_of_gold"]) / len(answerable_cases)
            if answerable_cases
            else None
        )
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else None

        report = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "pipeline": {
                "chunking": "server/services/chunkingService.js",
                "query": "server/services/vectorDbService.js",
                "embedding_model": "nomic-embed-text",
                "llm": "llama3.2",
                "temperature": 0.2,
                "top_k": TOP_K,
                "eval_collection": EVAL_COLLECTION,
                "production_collection_untouched": PROD_COLLECTION,
                "questions": len(cases),
                "limited": limit > 0,
            },
            "index_embed_ms": round(index_embed_ms, 1),
            "llm_warmup_ms": warmup["warmup_ms"],
            "retrieval": {
                "scope": "answerable questions, chunk level, top 4",
                "confusion_matrix": retrieval_cm,
                **rates(retrieval_cm),
                "macro_precision": None if macro_precision is None else round(macro_precision, 4),
                "macro_recall": None if macro_recall is None else round(macro_recall, 4),
                "hit_rate_at_4": None if hit_rate is None else round(hit_rate, 4),
                "mrr": None if mrr is None else round(mrr, 4),
            },
            "end_to_end": {
                "positive_class": "question is answerable and the answer states the gold fact",
                "confusion_matrix": end_to_end_cm,
                **rates(end_to_end_cm),
            },
            "answerability": {
                "positive_class": "model answered instead of abstaining",
                "confusion_matrix": abstain_cm,
                **rates(abstain_cm),
            },
            "llm_latency": {
                "wall_clock_invoke_ms": summarize_latency([case["llm_wall_ms"] for case in cases]),
                "generation_ms": summarize_latency([case["llm_generation_ms"] for case in cases if case["llm_generation_ms"] is not None]),
                "prompt_eval_ms": summarize_latency([case["llm_prompt_ms"] for case in cases if case["llm_prompt_ms"] is not None]),
                "load_ms": summarize_latency([case["llm_load_ms"] for case in cases if case["llm_load_ms"] is not None]),
                "embed_ms": summarize_latency([case["embed_ms"] for case in cases]),
                "chroma_query_ms": summarize_latency([case["retrieval_ms"] for case in cases]),
            },
            "cases": cases,
            "notes": [
                "Retrieval precision treats every non-gold chunk inside the top 4 as a false positive. With one relevant chunk, a perfect top-4 retrieval scores precision 0.25 and recall 1.",
                "End-to-end true positive: an answerable question whose answer includes the gold fact and does not abstain. False positive: an unanswerable question that is answered or that leaks the gold fact. True negative: a correct abstention. False negative: an answerable question that is missed or answered without the fact.",
                "LLM wall-clock latency is the time ChatOllama.invoke waits in the same call shape as queryDocumentRAG, after a warmup call. Generation latency is Ollama eval_duration when the client returns it.",
            ],
        }
        return report
    finally:
        try:
            if worker.proc.poll() is None:
                worker.request({"op": "cleanup"})
        except Exception as error:  # noqa: BLE001
            print(f"Eval collection cleanup failed: {error}", flush=True)
        worker.close()
        worker_path.unlink(missing_ok=True)


def print_report(report: dict) -> None:
    if report.get("chunk_check"):
        print(json.dumps(report, indent=2))
        return
    retrieval = report["retrieval"]
    end_to_end = report["end_to_end"]
    answerability = report["answerability"]
    print("\nRAG evaluation")
    print(f"Questions: {report['pipeline']['questions']}")
    print(f"Hit rate@{TOP_K}: {fmt_rate(retrieval['hit_rate_at_4'])}    MRR: {fmt_rate(retrieval['mrr'])}")
    print(
        f"Macro precision@{TOP_K}: {fmt_rate(retrieval['macro_precision'])}    "
        f"macro recall@{TOP_K}: {fmt_rate(retrieval['macro_recall'])}"
    )
    print_matrix("Retrieval confusion matrix (answerable questions, top 4 chunks)", retrieval["confusion_matrix"], "relevant", "not relevant")
    print_matrix("End-to-end confusion matrix", end_to_end["confusion_matrix"], "answerable", "unanswerable")
    print_matrix("LLM answerability confusion matrix", answerability["confusion_matrix"], "answered", "abstained")
    latency = report["llm_latency"]
    print_latency("LLM latency, wall clock of llama3.2 invoke", latency["wall_clock_invoke_ms"])
    print_latency("LLM latency, generation (Ollama eval_duration)", latency["generation_ms"])
    print_latency("LLM latency, prompt eval", latency["prompt_eval_ms"])
    print_latency("Query embedding latency", latency["embed_ms"])
    print_latency("Chroma query latency", latency["chroma_query_ms"])
    print(f"\nLLM warmup (excluded from the latency stats): {report['llm_warmup_ms']:.0f} ms")
    print("\nPer question")
    for case in report["cases"]:
        print(
            f"  {case['id']:<18} gold_rank={str(case['rank_of_gold']):<4} "
            f"P={fmt_rate(case['retrieval_precision'])} R={fmt_rate(case['retrieval_recall'])} "
            f"abstain={str(case['abstained']):<5} fact={str(case['fact_present']):<5} "
            f"llm={case['llm_wall_ms']:.0f} ms"
        )
        print(f"    Q: {case['question']}")
        print(f"    A: {case['answer'].replace(chr(10), ' ')}")
    for note in report["notes"]:
        print(f"\nNote: {note}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the document-assistant RAG pipeline.")
    parser.add_argument("--chunk-check", action="store_true", help="Only verify chunking and gold markers.")
    parser.add_argument("--limit", type=int, default=0, help="Score only the first N questions.")
    args = parser.parse_args()
    report = run(chunk_check=args.chunk_check, limit=args.limit)
    if not args.chunk_check:
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote {REPORT_PATH}")
    print_report(report)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
