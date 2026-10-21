"""Mock HR system connector: departments, staff and daily attendance.

Stands in for the HR system until real access is available, producing what the HR &
Workforce screen needs. Volumes follow the screen design (485 staff in five units).
Like the SMIS mock, the records are messy on purpose:

- dates in mixed formats, and spelling variants for categories, campuses, contract
  types and attendance codes
- a few duplicate attendance rows
- a few broken rows: staff in an unknown department, an impossible hire date,
  attendance for unknown staff, and an unknown attendance code

The same seed always produces the same records. Attendance covers the weekdays of the
30 days up to `as_of` (today by default), which is what the HR dashboard shows.
"""
import random
from datetime import date, timedelta

from . import Connector

# name, category as HR writes it, campus as HR writes it, location, staff,
# attendance rate, (absence code, how many away on the last day)
UNITS = [
    ("Academic & Curriculum Instruction", "Teaching Staff (Full-Time & Contract)",
     "Kibuli Main & Buwaate", "Kibuli Main & Buwaate", 205, 0.980, ("L", 4)),
    ("Boarding & Catering Operations", "Non-Teaching Support", "Kibuli Main Campus",
     "Kibuli Main Dining Complex", 95, 0.958, ("L", 3)),
    ("Transport & Fleet Management", "Drivers & Mechanical Technicians", "Multi-Campus",
     "Consolidated Transport Depot", 45, 0.977, ("T", 1)),
    ("Administration & Executive Support", "Administrative & Clerical", "KIBULI MAIN",
     "Kibuli Main Administrative Block", 80, 0.938, ("F", 7)),
    ("Facilities & Maintenance", "Technical, Security & Groundskeeping", "Multi-Campus",
     "Multi-Campus Grounds", 60, 0.966, ("L", 3)),
]
JOB_TITLES = {
    "Academic & Curriculum Instruction": ["Class Teacher", "Subject Teacher", "Head of Department"],
    "Boarding & Catering Operations": ["Cook", "Matron", "Kitchen Assistant", "Warden"],
    "Transport & Fleet Management": ["Driver", "Mechanic", "Fleet Supervisor"],
    "Administration & Executive Support": ["Accounts Assistant", "Secretary", "Registrar"],
    "Facilities & Maintenance": ["Security Guard", "Groundskeeper", "Electrician", "Plumber"],
}
CONTRACT_SPELLINGS = {
    "full_time": ["Full Time", "FULL-TIME", "FT", "Permanent"],
    "contract": ["Contract", "CT"],
    "part_time": ["Part-time", "PT"],
}
# synthetic names only
FIRST_NAMES = ["Aisha", "Brian", "Catherine", "David", "Esther", "Faith", "Godfrey", "Harriet",
               "Isaac", "Joan", "Kenneth", "Lydia", "Moses", "Naomi", "Oscar", "Patience",
               "Ronald", "Sarah", "Timothy", "Winnie"]
LAST_NAMES = ["Akello", "Byaruhanga", "Kato", "Mugisha", "Nakato", "Nambi", "Okello",
              "Ssempala", "Tumusiime", "Wasswa", "Namugga", "Kiggundu", "Atim", "Mukasa"]
PRESENT_SPELLINGS = ["P", "Present", "PRESENT"]
ABSENCE_SPELLINGS = {
    "L": ["L", "On Leave", "Leave"],
    "T": ["T", "Training"],
    "F": ["F", "Field", "Field duty"],
    "A": ["A", "Absent"],
}


class MockHRConnector(Connector):
    """Generates HR-system records. `scale` shrinks the staff numbers, e.g. 0.1 for tests."""

    source_code = "hr"

    def __init__(self, seed=2026, scale=1.0, as_of=None):
        self.seed = seed
        self.scale = scale
        self.as_of = as_of or date.today()
        self.injected = {}

    def _date(self, value):
        style = self.rng.randrange(3)
        if style == 0:
            return value.strftime("%d/%m/%Y")
        if style == 1:
            return value.isoformat()
        return value.strftime("%d %b %Y")

    def _note(self, problem):
        self.injected[problem] = self.injected.get(problem, 0) + 1

    def _weekdays(self):
        days = [self.as_of - timedelta(days=n) for n in range(29, -1, -1)]
        return [d for d in days if d.weekday() < 5]

    def fetch(self):
        self.rng = random.Random(self.seed)
        self.injected = {}
        yield from self._units()
        staff = list(self._staff())
        yield from staff
        yield from self._attendance(staff)

    def _units(self):
        for name, category, campus, location, *_ in UNITS:
            yield "unit", name, {
                "DeptName": name, "StaffCategory": category, "Campus": campus,
                "Location": location,
            }

    def _staff(self):
        number = 0
        for name, *_rest in UNITS:
            headcount = max(1, round(_rest[3] * self.scale))
            for _ in range(headcount):
                number += 1
                staff_no = f"GHS-{number:04d}"
                hired = date(2010, 1, 1) + timedelta(days=self.rng.randint(0, 5800))
                payload = {
                    "StaffNo": staff_no,
                    "FullName": f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}",
                    "Department": name,
                    "JobTitle": self.rng.choice(JOB_TITLES[name]),
                    "EmploymentType": self.rng.choice(
                        CONTRACT_SPELLINGS["full_time"] * 6 + CONTRACT_SPELLINGS["contract"] * 3
                        + CONTRACT_SPELLINGS["part_time"]
                    ),
                    "HireDate": self._date(hired),
                    "Status": self.rng.choice(["Active", "ACTIVE", "active"]),
                }
                yield "employee", staff_no, payload
        # a few leavers, kept on record but out of headcount
        for _ in range(max(1, round(6 * self.scale))):
            number += 1
            yield "employee", f"GHS-{number:04d}", {
                "StaffNo": f"GHS-{number:04d}", "FullName": "Former Staff Member",
                "Department": UNITS[1][0], "JobTitle": "Cook", "EmploymentType": "Contract",
                "HireDate": self._date(date(2015, 3, 1)), "Status": "Left",
            }
        # broken rows
        number += 1
        yield "employee", f"GHS-{number:04d}", {
            "StaffNo": f"GHS-{number:04d}", "FullName": "Unknown Department Staff",
            "Department": "Library Services", "JobTitle": "Librarian",
            "EmploymentType": "FT", "HireDate": "2019-01-07", "Status": "Active",
        }
        self._note("employee_unknown_department")
        number += 1
        yield "employee", f"GHS-{number:04d}", {
            "StaffNo": f"GHS-{number:04d}", "FullName": "Bad Date Staff",
            "Department": UNITS[0][0], "JobTitle": "Class Teacher", "EmploymentType": "FT",
            "HireDate": "30/02/2018", "Status": "Active",
        }
        self._note("employee_impossible_hire_date")

    def _attendance(self, staff):
        rates = {name: (rate, absence) for name, *_r, rate, absence in UNITS}
        days = self._weekdays()
        active = [(no, p) for _, no, p in staff
                  if p["Status"].lower() == "active" and p["Department"] in rates
                  and p["HireDate"] != "30/02/2018"]
        for day in days:
            last_day = day == days[-1]
            away_today = set()
            if last_day:  # match the design: e.g. "4 on Leave" in a unit today
                for name, (_, (_code, count)) in rates.items():
                    members = [no for no, p in active if p["Department"] == name]
                    away_today |= set(self.rng.sample(members, min(count, len(members))))
            for staff_no, payload in active:
                rate, (code, _count) = rates[payload["Department"]]
                if last_day:
                    present = staff_no not in away_today
                else:
                    present = self.rng.random() < rate
                status = (self.rng.choice(PRESENT_SPELLINGS) if present
                          else self.rng.choice(ABSENCE_SPELLINGS[code if last_day else
                                                                 self.rng.choice([code, "A"])]))
                yield "attendance", f"{staff_no}:{day.isoformat()}", {
                    "StaffNo": staff_no, "Date": self._date(day), "Status": status,
                }
        # duplicates, unknown staff, and an unknown code
        first_day = days[0]
        for staff_no, _ in active[:max(1, round(10 * self.scale))]:
            yield "attendance", f"{staff_no}:{first_day.isoformat()}", {
                "StaffNo": staff_no, "Date": self._date(first_day), "Status": "P",
            }
            self._note("duplicate_attendance")
        for n in range(3):
            yield "attendance", f"GHS-9{n:03d}:{first_day.isoformat()}", {
                "StaffNo": f"GHS-9{n:03d}", "Date": self._date(first_day), "Status": "P",
            }
            self._note("attendance_unknown_staff")
        staff_no = active[0][0]
        yield "attendance", f"{staff_no}:{days[1].isoformat()}-wfh", {
            "StaffNo": staff_no, "Date": self._date(days[1]), "Status": "WFH",
        }
        self._note("attendance_unknown_code")
