FUNCTIONAL_CLASS_NAMES: dict[int, str] = {
    1: "Interstate",
    2: "Principal Arterial - Freeway",
    3: "Principal Arterial - Other",
    4: "Minor Arterial",
    5: "Major Collector",
    6: "Minor Collector",
    7: "Local",
}

DAY_OF_WEEK: dict[int, str] = {
    1: "Sunday",
    2: "Monday",
    3: "Tuesday",
    4: "Wednesday",
    5: "Thursday",
    6: "Friday",
    7: "Saturday",
}

DAY_NAME_TO_INT: dict[str, int] = {v: k for k, v in DAY_OF_WEEK.items()}
