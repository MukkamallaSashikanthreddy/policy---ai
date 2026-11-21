from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sample_policies"
OUT.mkdir(exist_ok=True)
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="DocTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#15324B"), spaceAfter=8))
styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], textColor=colors.HexColor("#176B87"), spaceBefore=12, spaceAfter=5))
styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], leading=15, spaceAfter=7))


def build(filename: str, title: str, sections: list[tuple[str, list[str]]]) -> None:
    doc = SimpleDocTemplate(str(OUT / filename), pagesize=A4, rightMargin=22*mm, leftMargin=22*mm, topMargin=20*mm, bottomMargin=20*mm)
    story = [Paragraph(title, styles["DocTitle"]), Paragraph("SYNTHETIC DEMONSTRATION DOCUMENT — NOT A REAL INSURANCE CONTRACT", styles["Italic"]), Spacer(1, 8)]
    for heading, paragraphs in sections:
        story.append(Paragraph(heading, styles["Section"]))
        for paragraph in paragraphs:
            story.append(Paragraph(paragraph, styles["BodySmall"]))
    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(22*mm, 10*mm, "PolicyLens synthetic sample — educational use only")
        canvas.drawRightString(A4[0] - 22*mm, 10*mm, f"Page {_doc.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


build(
    "sample_motor_policy_wording.pdf",
    "SampleShield Private Car Package Policy — Policy Wording",
    [
        ("1. Own-damage cover", [
            "Subject to the terms, conditions, exclusions and limits of this policy, the insurer will indemnify the insured for accidental loss of or damage to the insured vehicle caused by accidental external means.",
            "Insured events include fire, explosion, self-ignition or lightning; burglary or theft; riot and strike; malicious acts; terrorism; earthquake; flood, inundation, storm, cyclone, hurricane, tempest, typhoon, hailstorm or frost; landslide or rockslide; and loss or damage while the vehicle is in transit by road, rail, inland waterway, lift, elevator or air.",
        ]),
        ("2. Third-party liability", [
            "Subject to the policy terms and applicable law, the policy covers the insured's legal liability for death or bodily injury to a third party and damage to third-party property arising from use of the insured vehicle. Limits and statutory requirements apply.",
        ]),
        ("3. Important exclusions", [
            "The insurer will not pay for ordinary wear and tear, gradual deterioration, depreciation, or mechanical or electrical breakdown. This mechanical breakdown exclusion does not remove cover for accidental damage that is otherwise insured under this policy.",
            "Loss or damage is excluded when the vehicle is used outside the geographical area, for a purpose not permitted by the policy, for racing or speed testing, or while the vehicle is driven by a person who does not hold an effective and valid driving licence. Loss while the driver is under the influence of alcohol or drugs is excluded.",
            "Consequential loss, loss of use, and any amount arising solely from delay are not covered unless an endorsement expressly provides otherwise. The policy does not cover contractual liability beyond liability imposed by law.",
        ]),
        ("4. Claims conditions", [
            "The insured must give prompt notice of an event that may give rise to a claim and provide the insurer with the information and assistance reasonably requested. In the event of theft or an event involving injury or third-party property damage, the insured should also notify the police as soon as practicable.",
            "The insured must take reasonable steps to protect the vehicle from further loss. The insurer may appoint a surveyor or loss assessor and must be given a reasonable opportunity to inspect the vehicle before repairs begin, except for emergency steps reasonably required to prevent further damage.",
            "The insured must not admit liability, make an offer, promise payment or settle a third-party claim without the insurer's prior written consent. Payment remains subject to policy terms, deductibles, limits, verification and the insurer's assessment.",
        ]),
        ("5. General interpretation", [
            "This synthetic wording is a training example only. It does not represent an actual insurer's product and must not be used to decide a real claim. Where wording is unclear, the complete issued contract and insurer confirmation control.",
        ]),
    ],
)

build(
    "sample_motor_policy_schedule.pdf",
    "SampleShield Private Car Package Policy — Policy Schedule",
    [
        ("1. Insured vehicle and period", [
            "Policyholder: Alex Example (synthetic). Vehicle: Private car, sample registration TN-00-XX-0000. Policy number: DEMO-MOTOR-2026-001. Policy period: 1 January 2026 to 31 December 2026, both days inclusive.",
            "Insured declared value (IDV): INR 8,00,000. This value is the schedule's stated insured declared value and is subject to policy terms, depreciation provisions, applicable limits and claim assessment.",
        ]),
        ("2. Deductible and excess", [
            "A compulsory deductible of INR 1,000 applies to each own-damage claim, unless a different amount is required by an endorsement or applicable policy term. Voluntary deductible: Nil. The insured bears the applicable deductible; it is not reimbursed by this schedule.",
        ]),
        ("3. Selected add-on", [
            "Roadside Assistance add-on: INCLUDED. The service operates 24 hours a day, subject to service availability and the add-on terms. For an eligible breakdown, towing to the nearest network garage is available up to 50 kilometres per event. Additional distance, non-network destination requests and costs not listed in the add-on are subject to confirmation and may be charged to the customer.",
            "No zero-depreciation / nil-depreciation add-on is listed as included in this synthetic schedule. An add-on not shown as included should not be assumed to be part of the cover.",
        ]),
        ("4. Schedule caveat", [
            "This is a synthetic schedule generated for a software demonstration. It is not an issued policy, quote, certificate of insurance or evidence of real coverage.",
        ]),
    ],
)

build(
    "sample_claim_guide.pdf",
    "SampleShield Motor Insurance — Claim Intimation and Document Guide",
    [
        ("1. Claim intimation", [
            "For accidental damage, notify the insurer as soon as possible and preferably within 24 hours of the incident. For theft, inform the police and insurer as soon as practicable. Delays should be explained and may be reviewed under the policy conditions.",
            "Provide the policy number, date and approximate time of incident, vehicle location, a short description of what happened, contact details and photographs when safely available. Do not admit liability or agree to a settlement with another party before speaking with the insurer.",
        ]),
        ("2. Common own-damage claim documents", [
            "The claim guide lists the following documents for an own-damage claim: completed claim form; policy schedule or policy details; valid driving licence of the person driving at the time; vehicle registration certificate (RC); repair estimate from the garage; and final repair invoice and payment receipt when repairs are completed.",
            "The insurer may request original documents for verification or additional information reasonably related to the claim. A surveyor may inspect the vehicle and assess the loss before repair authorization is issued.",
        ]),
        ("3. Additional documents for theft", [
            "For a theft claim, submit a copy of the first information report (FIR) or police complaint acknowledgement and all available sets of vehicle keys. A non-traceable certificate or final police report may be requested when issued by the police. The insurer may ask for further police records or forms depending on the case.",
        ]),
        ("4. Third-party claim documents", [
            "For a third-party injury or property damage event, provide the police report or FIR where registered, notices or court documents received, details of the other party, and available evidence about the incident. Forward legal notices to the insurer promptly and do not independently admit or settle liability.",
        ]),
        ("5. Claim handling steps", [
            "The general process is: register the claim and receive a reference number; submit the initial information and applicable documents; make the vehicle available for inspection by the insurer's surveyor; obtain repair authorization where required; submit final bills; and allow the insurer to assess the claim under the policy terms.",
            "A document checklist is indicative and may vary with claim type, facts, law and insurer verification. Submission of documents does not guarantee claim acceptance or payment.",
        ]),
        ("6. Demonstration notice", [
            "This synthetic claim guide is for PolicyLens testing only. It is not an actual insurer's claim instruction or a substitute for the issued policy and insurer guidance.",
        ]),
    ],
)
print(f"Generated sample PDFs in {OUT}")
