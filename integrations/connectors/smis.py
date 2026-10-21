"""Mock SMIS connector: realistic, deliberately messy school records.

It stands in for the schools' SMIS until real access is available, producing what the
Student Enrollment and Student Retention screens need: schools, terms, students,
enrolments and admissions applications. Records use SMIS-style field names and the
kind of mess real exports have, so the cleaning and loading steps are properly tested:

- dates in mixed formats (17/10/2015, 2015-10-17, 17 Oct 2015)
- spelling variants for campuses, gender, nationality, terms and statuses
- free-text withdrawal reasons
- a few duplicate student rows
- a few broken rows: impossible dates, missing gender, enrolments for unknown students,
  applications at an unknown stage

The same seed always produces the same records.
"""
import random
from datetime import date, timedelta

from . import Connector

# code, name, campus, students this term, capacity
SCHOOLS = [
    ("GHA-NK", "GreenHill Academy Nursery Kibuli", "kibuli", 260, 290),
    ("GHA-PK", "GreenHill Academy Primary Kibuli", "kibuli", 560, 610),
    ("GHA-SK", "Green Hill Academy Secondary School Kibuli", "kibuli", 430, 470),
    ("GHA-NB", "GreenHill Academy Nursery Buwaate", "buwaate", 230, 260),
    ("GHA-PB", "GreenHill Academy Primary Buwaate", "buwaate", 620, 670),
    ("GHA-AX", "Annex Preschool", "annex", 700, 770),
]
CLASSES = {
    "GHA-NK": ["Baby", "Middle", "Top"], "GHA-NB": ["Baby", "Middle", "Top"],
    "GHA-AX": ["Baby", "Middle", "Top"],
    "GHA-PK": [f"P{n}" for n in range(1, 8)], "GHA-PB": [f"P{n}" for n in range(1, 8)],
    "GHA-SK": [f"S{n}" for n in range(1, 7)],
}
# year, term number, start, end; the current year runs to Term 3 2026
TERMS = [
    ("2025", 3, date(2025, 9, 15), date(2025, 12, 5)),
    ("2026", 1, date(2026, 2, 2), date(2026, 4, 30)),
    ("2026", 2, date(2026, 5, 25), date(2026, 8, 14)),
    ("2026", 3, date(2026, 9, 14), date(2026, 12, 4)),
]

# How SMIS might write the same thing differently from row to row.
SECTION_SPELLINGS = {
    "nursery": ["Nursery", "NURSERY", "Pre-primary", "Kindergarten"],
    "primary": ["Primary", "PRIMARY", "Pri"],
    "secondary": ["Secondary", "SECONDARY", "Sec", "O & A Level"],
}
LEVEL_OF_SCHOOL = {"GHA-NK": "nursery", "GHA-NB": "nursery", "GHA-AX": "nursery",
                   "GHA-PK": "primary", "GHA-PB": "primary", "GHA-SK": "secondary"}
CAMPUS_SPELLINGS = {
    "kibuli": ["Kibuli Main Campus", "KIBULI MAIN ", "Kibuli", "kibuli main"],
    "buwaate": ["Buwaate Campus", "BUWAATE", "Buwate", "buwaate"],
    "annex": ["Annex / Preschool Branch", "Annex Preschool", "ANNEX"],
}
SEX_SPELLINGS = {"male": ["M", "Male", "MALE", "boy"], "female": ["F", "Female", "FEMALE", "girl"]}
NATIONALITY_SPELLINGS = [
    (0.76, ["UG", "Uganda", "Ugandan", "uganda"]),
    (0.12, ["KE", "Kenya", "Kenyan"]),
    (0.08, ["RW", "Rwanda", "Rwandese"]),
    (0.04, ["SS", "South Sudan", "Burundi", "DRC"]),
]
TERM_SPELLINGS = ["Term {n}", "T{n}", "TERM {n}", "{roman}"]
ROMAN = {1: "I", 2: "II", 3: "III"}
STATUS_SPELLINGS = {
    "active": ["Active", "ACTIVE", "active"],
    "withdrawn": ["Withdrawn", "WITHDRAWN", "Left"],
    "graduated": ["Completed", "Graduated", "COMPLETED"],
}
# our reason code: how SMIS staff typed it
WITHDRAWAL_REASONS = [
    ("financial", 44, ["Fees", "Financial constraints", "School fees challenges"]),
    ("transfer", 34, ["Transferred", "Transfer to another school", "Moved school"]),
    ("death", 23, ["Deceased", "Death"]),
    ("academic_performance", 23, ["Poor performance", "Academic performance"]),
]
STAGE_SPELLINGS = {
    "applied": ["Applied", "APPLIED", "New application"],
    "qualified": ["Qualified", "Shortlisted"],
    "interviewed": ["Interviewed", "Interview done"],
    "accepted": ["Accepted", "Offer accepted"],
    "enrolled": ["Enrolled", "Joined"],
}
FUNNEL = [("applied", 900), ("qualified", 460), ("interviewed", 300), ("accepted", 240),
          ("enrolled", 190)]
# rough birth year of a school's pupils, so dates of birth look right for each level
BORN_AROUND = {
    "GHA-NK": date(2021, 6, 1), "GHA-NB": date(2021, 6, 1), "GHA-AX": date(2021, 6, 1),
    "GHA-PK": date(2016, 6, 1), "GHA-PB": date(2016, 6, 1), "GHA-SK": date(2011, 6, 1),
}
RETURN_RATE = 0.885
GRADUATE_SHARE = 0.10
AT_RISK = 150


class MockSMISConnector(Connector):
    """Generates SMIS-style records. `scale` shrinks the volumes, e.g. 0.05 for tests."""

    source_code = "smis"

    def __init__(self, seed=2026, scale=1.0):
        self.seed = seed
        self.scale = scale
        # how many broken or duplicate rows were put in, so tests can check they're caught
        self.injected = {}

    # --- writing values the way SMIS might ---

    def _date(self, value):
        style = self.rng.randrange(4)
        if style == 0:
            return value.strftime("%d/%m/%Y")
        if style == 1:
            return value.isoformat()
        if style == 2:
            return value.strftime("%d %b %Y")
        return value.strftime("%d-%m-%Y")

    def _term_code(self, year, number):
        return f"{year}-T{number}"

    def _count(self, value):
        return max(1, round(value * self.scale))

    def _note(self, problem):
        self.injected[problem] = self.injected.get(problem, 0) + 1

    def _nationality(self):
        r, total = self.rng.random(), 0.0
        for share, spellings in NATIONALITY_SPELLINGS:
            total += share
            if r < total:
                return self.rng.choice(spellings)
        return "UG"

    # --- the records ---

    def fetch(self):
        self.rng = random.Random(self.seed)
        # Fields added later draw from their own generator, so the records that already
        # existed keep exactly the same values for the same seed.
        self.extra_rng = random.Random(self.seed + 1)
        self.injected = {}
        self._admission_counter = 0
        yield from self._schools()
        yield from self._terms()
        students, enrolments = self._students_and_enrolments()
        yield from students
        yield from enrolments
        yield from self._applications()

    def _schools(self):
        for code, name, campus, _, capacity in SCHOOLS:
            yield "school", code, {
                "SchoolCode": code,
                "SchoolName": f" {name} " if self.rng.random() < 0.2 else name,
                "Campus": self.rng.choice(CAMPUS_SPELLINGS[campus]),
                "Capacity": str(self._count(capacity)),
                "Section": self.extra_rng.choice(SECTION_SPELLINGS[LEVEL_OF_SCHOOL[code]]),
            }

    def _terms(self):
        for year, number, start, end in TERMS:
            label = self.rng.choice(TERM_SPELLINGS).format(n=number, roman=ROMAN[number])
            yield "term", self._term_code(year, number), {
                "TermCode": self._term_code(year, number),
                "AcademicYear": year,
                "Term": label,
                "StartDate": self._date(start),
                "EndDate": self._date(end),
            }

    def _new_student(self, school_code, born_around):
        self._admission_counter += 1
        admission_no = f"GH/{born_around.year + 4}/{self._admission_counter:05d}"
        sex = self.rng.choice(["male", "female"])
        dob = born_around + timedelta(days=self.rng.randint(-200, 200))
        payload = {
            "AdmissionNo": admission_no,
            "Sex": self.rng.choice(SEX_SPELLINGS[sex]),
            "Nationality": self._nationality(),
            "DOB": self._date(dob),
            "HomeSchool": school_code,
        }
        # a few broken rows that cleaning must reject
        roll = self.rng.random()
        if roll < 0.003:
            payload["Sex"] = ""
            self._note("student_missing_sex")
        elif roll < 0.006:
            payload["DOB"] = "31/02/2014"
            self._note("student_impossible_dob")
        return admission_no, payload

    def _students_and_enrolments(self):
        terms = {(y, n): self._term_code(y, n) for y, n, _, _ in TERMS}
        last_year = terms[("2025", 3)]
        this_year = [terms[("2026", 1)], terms[("2026", 2)], terms[("2026", 3)]]
        students, enrolments = [], []
        enrolment_counter = 0

        def enrol(admission_no, school_code, term_code, status="active", reason="", at_risk=False):
            nonlocal enrolment_counter
            enrolment_counter += 1
            payload = {
                "EnrolmentID": f"EN-{enrolment_counter:06d}",
                "AdmissionNo": admission_no,
                "SchoolCode": school_code,
                "TermCode": term_code,
                "Class": self.rng.choice(CLASSES[school_code]),
                "Status": self.rng.choice(STATUS_SPELLINGS[status]),
                "WithdrawalDate": "",
                "WithdrawalReason": reason,
                "AtRisk": self.rng.choice(["Y", "Yes", "1"]) if at_risk
                else self.rng.choice(["N", "No", "", "0"]),
            }
            enrolments.append(("enrolment", payload["EnrolmentID"], payload))
            return payload

        returners_all = []
        for code, _, _, active_now, _ in SCHOOLS:
            active_now = self._count(active_now)
            returning = int(active_now * 0.80)
            eligible = int(returning / RETURN_RATE)
            graduates = int(eligible * GRADUATE_SHARE / (1 - GRADUATE_SHARE))
            born = BORN_AROUND[code]

            last = [self._new_student(code, born) for _ in range(eligible + graduates)]
            self.rng.shuffle(last)
            for i, (admission_no, payload) in enumerate(last):
                students.append(("student", admission_no, payload))
                enrol(admission_no, code, last_year,
                      status="graduated" if i >= eligible else "active")
            returners_all += [(admission_no, code) for admission_no, _ in last[:returning]]

            for _ in range(active_now - returning):
                admission_no, payload = self._new_student(code, born)
                students.append(("student", admission_no, payload))
                joined = this_year if self.rng.random() < 0.85 else this_year[2:]
                for term_code in joined:
                    enrol(admission_no, code, term_code)

        # Returners: some withdraw during the year, with free-text reasons.
        self.rng.shuffle(returners_all)
        leaving = {}
        pool = list(returners_all)
        for _, count, spellings in WITHDRAWAL_REASONS:
            for _ in range(self._count(count)):
                if pool:
                    leaving[pool.pop()] = (self.rng.choice(spellings), self.rng.randrange(3))
        for _ in range(self._count(4)):  # reasons with no clear category
            if pool:
                leaving[pool.pop()] = ("Relocated abroad", self.rng.randrange(3))

        current_active = []
        for key in returners_all:
            admission_no, code = key
            leave = leaving.get(key)
            for index, term_code in enumerate(this_year):
                if leave and index == leave[1]:
                    payload = enrol(admission_no, code, term_code, "withdrawn", leave[0])
                    payload["WithdrawalDate"] = self._date(TERMS[index + 1][2] + timedelta(days=20))
                    break
                payload = enrol(admission_no, code, term_code)
                if index == 2:
                    current_active.append(payload)

        at_risk = min(self._count(AT_RISK), len(current_active))
        for payload in self.rng.sample(current_active, at_risk):
            payload["AtRisk"] = self.rng.choice(["Y", "Yes", "1"])

        # Duplicate student rows, and enrolments for students SMIS doesn't list.
        for _ in range(self._count(15)):
            students.append(self.rng.choice(students))
            self._note("duplicate_student")
        for _ in range(self._count(6)):
            enrol(f"GH/0000/{self.rng.randint(90000, 99999)}", "GHA-PK", this_year[2])
            self._note("enrolment_unknown_student")
        return students, enrolments

    def _applications(self):
        counts = [self._count(n) for _, n in FUNNEL]
        number = 0
        for i, (stage, _) in enumerate(FUNNEL):
            at_stage = counts[i] - (counts[i + 1] if i + 1 < len(FUNNEL) else 0)
            for _ in range(max(0, at_stage)):
                number += 1
                code = self.rng.choice(SCHOOLS)[0]
                applied = date(2026, self.rng.randint(6, 8), self.rng.randint(1, 28))
                yield "application", f"APP/2026/{number:05d}", {
                    "ApplicationNo": f"APP/2026/{number:05d}",
                    "SchoolCode": code,
                    "TermCode": self._term_code("2026", 3),
                    "Stage": self.rng.choice(STAGE_SPELLINGS[stage]),
                    "DateApplied": self._date(applied),
                }
        for _ in range(self._count(5)):
            number += 1
            yield "application", f"APP/2026/{number:05d}", {
                "ApplicationNo": f"APP/2026/{number:05d}",
                "SchoolCode": "GHA-PB",
                "TermCode": self._term_code("2026", 3),
                "Stage": "Waitlisted",  # not a stage we track: must be rejected
                "DateApplied": self._date(date(2026, 8, 10)),
            }
            self._note("application_unknown_stage")
