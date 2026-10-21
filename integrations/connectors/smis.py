"""Mock SMIS connector: realistic, deliberately messy school records.

It stands in for the schools' SMIS until real access is available, producing what the
Student Enrollment, Student Retention and Academic Performance screens need: schools,
terms, students, enrolments, admissions applications, subjects, tests and exams with
each student's mark, syllabus coverage, and PLE/UCE/UACE results. Records use
SMIS-style field names and the kind of mess real exports have, so the cleaning and
loading steps are properly tested:

- dates in mixed formats (17/10/2015, 2015-10-17, 17 Oct 2015)
- spelling variants for campuses, gender, nationality, terms, statuses, subject levels,
  test names ("BOT", "Test 1"), exams ("P.L.E") and divisions ("DIV II", "2")
- marks written as "67", "67.5", "67%" or " 67 "
- free-text withdrawal reasons
- a few duplicate student and result rows
- a few broken rows: impossible dates, missing gender, enrolments for unknown students,
  applications at an unknown stage, absent ("ABS") or impossible (105) marks, more
  syllabus topics covered than planned, a PLE aggregate of 41, an exam division "X"

The performance records come from a separate random generator, after everything else,
so adding them did not change any of the earlier records.

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

# --- Academic performance ---
# code, name, category, how much easier (+) or harder (-) than average the subject marks
SUBJECTS = {
    "primary": [
        ("ENG", "English", "arts", 4), ("MTC", "Mathematics", "science", -5),
        ("SCI", "Integrated Science", "science", -1), ("SST", "Social Studies", "arts", 2),
    ],
    "o_level": [
        ("ENG", "English Language", "arts", 6), ("MTC", "Mathematics", "science", -4),
        ("BIO", "Biology", "science", 2), ("CHE", "Chemistry", "science", -5),
        ("PHY", "Physics", "science", -7), ("HIS", "History", "arts", 3),
        ("GEO", "Geography", "arts", 0),
    ],
    "a_level": [
        ("GP", "General Paper", "arts", 5), ("MTC", "Mathematics", "science", -2),
        ("PHY", "Physics", "science", -4), ("CHE", "Chemistry", "science", -3),
        ("BIO", "Biology", "science", 1), ("ECO", "Economics", "arts", 2),
        ("HIS", "History", "arts", 3), ("GEO", "Geography", "arts", 0),
        ("LIT", "Literature in English", "arts", 4),
    ],
}
# A-level students take General Paper plus one of these combinations.
A_LEVEL_COMBINATIONS = [("PHY", "CHE", "MTC"), ("BIO", "CHE", "MTC"), ("HIS", "ECO", "GEO"),
                        ("HIS", "LIT", "GEO"), ("ECO", "GEO", "MTC")]
SUBJECT_LEVEL_SPELLINGS = {
    "primary": ["Primary", "PRI", "primary"],
    "o_level": ["O Level", "O-Level", "UCE", "Ordinary"],
    "a_level": ["A Level", "A-Level", "UACE", "Advanced"],
}
CATEGORY_SPELLINGS = {"science": ["Science", "Sciences", "SCI"],
                      "arts": ["Arts", "Humanities", "ARTS"]}
KIND_SPELLINGS = {
    "test_1": ["Test 1", "TEST 1", "Test One", "BOT"],
    "test_2": ["Test 2", "TEST 2", "Test Two", "MOT"],
    "end_of_term": ["End of Term", "EOT", "End Term Exam"],
}
# Which assessments each term has had so far (Term 3 is still running), and when.
ASSESSMENT_PLAN = [
    ("2026", 2, [("test_1", date(2026, 6, 12)), ("test_2", date(2026, 7, 10)),
                 ("end_of_term", date(2026, 8, 5))]),
    ("2026", 3, [("test_1", date(2026, 9, 30)), ("test_2", date(2026, 10, 16))]),
]
TERM_IMPROVEMENT = {2: 0.0, 3: 2.0}  # marks rise a little from Term 2 to Term 3
EXAM_SPELLINGS = {"ple": ["PLE", "P.L.E", "ple"], "uce": ["UCE", "U.C.E", "O Level"],
                  "uace": ["UACE", "U.A.C.E", "A Level"]}
DIVISION_SPELLINGS = {
    "division_1": ["Div 1", "DIV I", "1", "Division 1"],
    "division_2": ["Div 2", "DIV II", "2", "Division 2"],
    "division_3": ["Div 3", "DIV III", "3", "Division 3"],
    "division_4": ["Div 4", "DIV IV", "4", "Division 4"],
    "ungraded": ["U", "Ungraded", "DIV U"],
}


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
        self.perf_rng = random.Random(self.seed + 2)
        self.injected = {}
        self._admission_counter = 0
        self._placements = []  # (admission no, school, term, class, status) per enrolment
        yield from self._schools()
        yield from self._terms()
        students, enrolments = self._students_and_enrolments()
        yield from students
        yield from enrolments
        yield from self._applications()
        yield from self._performance()

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
            self._placements.append(
                (admission_no, school_code, term_code, payload["Class"], status)
            )
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

    # --- academic performance ---

    @staticmethod
    def subject_level(class_level):
        """Which subject level a class sits: P4-P7 primary, S1-S4 O level, S5-S6 A level.
        Nursery and P1-P3 (the thematic curriculum) have no graded subjects."""
        if class_level in ("P4", "P5", "P6", "P7"):
            return "primary"
        if class_level in ("S1", "S2", "S3", "S4"):
            return "o_level"
        if class_level in ("S5", "S6"):
            return "a_level"
        return None

    def _ability(self, admission_no):
        """Each student's usual mark, so their results hang together across subjects."""
        if admission_no not in self._abilities:
            self._abilities[admission_no] = self.perf_rng.gauss(60, 13)
        return self._abilities[admission_no]

    def _mark(self, value):
        """A mark written the way a teacher's marksheet might have it."""
        value = min(100.0, max(0.0, value))
        style = self.perf_rng.randrange(4)
        if style == 0:
            return f"{value:.0f}"
        if style == 1:
            return f"{value:.1f}"
        if style == 2:
            return f"{value:.0f}%"
        return f" {value:.0f} "

    def _performance(self):
        rng = self.perf_rng
        self._abilities = {}
        known = [p for p in self._placements if not p[0].startswith("GH/0000/")]

        # Subjects.
        for level, subjects in SUBJECTS.items():
            for code, name, category, _ in subjects:
                yield "subject", f"{level}:{code}", {
                    "SubjectCode": code,
                    "SubjectName": name,
                    "Level": rng.choice(SUBJECT_LEVEL_SPELLINGS[level]),
                    "Category": rng.choice(CATEGORY_SPELLINGS[category]),
                }

        # Who sits in which class each term, and each A-level student's combination.
        classes = {}
        for admission_no, school, term_code, class_level, status in known:
            if status == "active" and self.subject_level(class_level):
                classes.setdefault((school, term_code, class_level), []).append(admission_no)
        combination = {}

        def takes(admission_no, level, code):
            if level != "a_level" or code == "GP":
                return True
            if admission_no not in combination:
                combination[admission_no] = rng.choice(A_LEVEL_COMBINATIONS)
            return code in combination[admission_no]

        # Assessments, results and syllabus coverage for Terms 2 and 3 of 2026.
        result_counter = 0
        coverage_counter = 0
        results = []
        for year, number, sittings in ASSESSMENT_PLAN:
            term_code = self._term_code(year, number)
            for (school, code_of_term, class_level), pupils in sorted(classes.items()):
                if code_of_term != term_code:
                    continue
                level = self.subject_level(class_level)
                for code, _, _, offset in SUBJECTS[level]:
                    coverage_counter += 1
                    planned = rng.randint(12, 20)
                    share = rng.uniform(0.85, 1.0) if number == 2 else rng.uniform(0.45, 0.7)
                    covered = round(planned * share)
                    if rng.random() < 0.01:  # a typing slip: more topics covered than planned
                        covered = planned + 3
                        self._note("syllabus_covered_exceeds_planned")
                    yield "syllabus", f"SY-{coverage_counter:05d}", {
                        "CoverageID": f"SY-{coverage_counter:05d}",
                        "SchoolCode": school,
                        "TermCode": term_code,
                        "Class": class_level,
                        "SubjectCode": code,
                        "TopicsPlanned": str(planned),
                        "TopicsCovered": str(covered),
                    }
                    for kind, held_on in sittings:
                        assessment_id = f"AS-{term_code}-{school}-{class_level}-{code}-{kind}"
                        yield "assessment", assessment_id, {
                            "AssessmentID": assessment_id,
                            "SchoolCode": school,
                            "TermCode": term_code,
                            "Class": class_level,
                            "SubjectCode": code,
                            "Kind": rng.choice(KIND_SPELLINGS[kind]),
                            "DateHeld": self._date(held_on),
                        }
                        for admission_no in pupils:
                            if not takes(admission_no, level, code):
                                continue
                            result_counter += 1
                            mark = (self._ability(admission_no) + offset
                                    + TERM_IMPROVEMENT[number] + rng.gauss(0, 8))
                            payload = {
                                "ResultID": f"RS-{result_counter:07d}",
                                "AssessmentID": assessment_id,
                                "AdmissionNo": admission_no,
                                "Mark": self._mark(mark),
                            }
                            roll = rng.random()
                            if roll < 0.002:
                                payload["Mark"] = "ABS"  # absent: no mark to record
                                self._note("result_absent")
                            elif roll < 0.003:
                                payload["Mark"] = "105"  # out of range
                                self._note("result_mark_out_of_range")
                            results.append(("result", payload["ResultID"], payload))
        for _ in range(self._count(10)):
            results.append(rng.choice(results))
            self._note("duplicate_result")
        yield from results

        # National examinations sat at the end of 2025 by last year's P7, S4 and S6.
        exam_of_class = {"P7": "ple", "S4": "uce", "S6": "uace"}
        exam_counter = 0
        for admission_no, school, term_code, class_level, _ in known:
            exam = exam_of_class.get(class_level)
            if term_code != self._term_code("2025", 3) or exam is None:
                continue
            exam_counter += 1
            ability = self._ability(admission_no) + rng.gauss(0, 6)
            payload = {
                "ExamResultID": f"NX-{exam_counter:05d}",
                "AdmissionNo": admission_no,
                "SchoolCode": school,
                "Exam": rng.choice(EXAM_SPELLINGS[exam]),
                "Year": "2025",
                "Division": "",
                "Aggregate": "",
                "PrincipalPasses": "",
            }
            if exam == "ple":
                aggregate = min(36, max(4, round(4 + (100 - ability) * 0.42)))
                division = ("division_1" if aggregate <= 12 else "division_2" if aggregate <= 23
                            else "division_3" if aggregate <= 29 else "division_4"
                            if aggregate <= 34 else "ungraded")
                payload["Aggregate"] = str(aggregate)
                payload["Division"] = rng.choice(DIVISION_SPELLINGS[division])
            elif exam == "uce":
                division = ("division_1" if ability >= 72 else "division_2" if ability >= 60
                            else "division_3" if ability >= 50 else "division_4"
                            if ability >= 40 else "ungraded")
                payload["Division"] = rng.choice(DIVISION_SPELLINGS[division])
            else:
                passes = 3 if ability >= 62 else 2 if ability >= 50 else 1 if ability >= 40 else 0
                payload["PrincipalPasses"] = str(passes)
            roll = rng.random()
            if exam == "ple" and roll < 0.01:
                payload["Aggregate"] = "41"  # outside 4 to 36
                self._note("exam_aggregate_out_of_range")
            elif exam != "uace" and roll < 0.02:
                payload["Division"] = "X"  # absent from the exam: no result
                self._note("exam_division_unknown")
            yield "exam_result", payload["ExamResultID"], payload
