from __future__ import annotations

import re

from vz_search.domain.entities import ExtractedPerson
from vz_search.infrastructure.text_processing import detect_state

# Encabezados / ruido frecuente en listas hospitalarias
_JUNK_WORDS = frozenset(
    {
        "hospital",
        "apellidos",
        "nombres",
        "nombre",
        "apellido",
        "edad",
        "cedula",
        "cédula",
        "telefono",
        "teléfono",
        "cama",
        "direccion",
        "dirección",
        "trauma",
        "emergencia",
        "pediatria",
        "pediatría",
        "hospitalizacion",
        "hospitalización",
        "ctrl",
        "buscar",
        "lista",
        "actualizada",
        "registro",
        "maestro",
        "notas",
        "procedentes",
        "tomografia",
        "terapia",
        "parto",
        "sala",
        "poli",
        "merqencia",
        "shock",
        "pasillo",
        "femenino",
        "masculino",
        "masculinos",
        "mujeres",
        "nueva",
        "nueua",
        "fecha",
        "hora",
    }
)

_JUNK_LINE_RE = re.compile(
    r"(?:^|\b)(?:n[°º]|#cama|c\.?\s*\d|para buscar|use ctrl|apellidos y nombres|nombre y apellido)",
    re.IGNORECASE,
)

_HOSPITAL_ROW_RE = re.compile(
    r"^(\d+)\s+(Hospital\s+.+)$",
    re.IGNORECASE,
)

_PIPE_TABLE_ROW_RE = re.compile(
    r"(\d+)\s+(Hospital[^|]+?)\s*\|\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s'\-/\.]+?)\s*\|\s*(\d{1,3})\b",
)

_CAPS_NAME_RE = re.compile(
    r"^[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s'\-/\.]{2,}$",
)

_TITLE_NAME_RE = re.compile(
    r"^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3}$",
)

_MERGED_NAME_RE = re.compile(r"^[A-Z][a-z]+[A-Z][a-z]+(?:[A-Z][a-z]+)?$")

_AGE_ONLY_RE = re.compile(r"^\d{1,3}a?(?:nos|ños|fios)?$", re.IGNORECASE)

_LOCATION_RE = re.compile(r"^(?:la guaira|caracas|miranda|los caracas|la guaira:)", re.IGNORECASE)


def normalize_person_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name.strip())
    if _MERGED_NAME_RE.match(name):
        name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    if name.isupper() or sum(c.isupper() for c in name) > len(name) * 0.7:
        name = name.title()
    return name[:80]


def is_plausible_person_name(name: str) -> bool:
    name = name.strip()
    if len(name) < 4 or len(name) > 80:
        return False
    if re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", name):
        return False
    if _JUNK_LINE_RE.search(name):
        return False
    if _LOCATION_RE.search(name):
        return False
    if re.search(r"\d", name):
        return False
    if "|" in name or "—" in name or "一" in name:
        return False

    words = [w for w in re.split(r"\s+", name) if w]
    if len(words) < 2 or len(words) > 5:
        return False

    alpha = sum(c.isalpha() for c in name)
    if alpha < len(name) * 0.6:
        return False

    lower_words = [w.lower().strip(".,;:") for w in words]
    if any(w in _JUNK_WORDS for w in lower_words):
        return False
    if sum(w in _JUNK_WORDS for w in lower_words) >= 2:
        return False

    # Evitar frases tipo "Los Caracas / La"
    if lower_words[0] in {"los", "las", "la", "el", "para", "sala", "lista"}:
        return False

    return True


def _person_from_parts(
    name: str,
    *,
    hospital: str | None,
    age: str | None = None,
    extra: str | None = None,
    strict: bool = True,
) -> ExtractedPerson | None:
    name = normalize_person_name(name)
    if strict and not is_plausible_person_name(name):
        return None
    if not strict:
        words = name.split()
        if len(words) < 2 or any(ch.isdigit() for ch in name):
            return None

    state = detect_state(hospital or "") or detect_state(extra or "")
    notes_parts: list[str] = []
    if age:
        notes_parts.append(f"Edad: {age}")
    if extra:
        notes_parts.append(extra[:300])
    return ExtractedPerson(
        full_name=name,
        hospital=hospital,
        state=state,
        age=age,
        notes=" | ".join(notes_parts) if notes_parts else None,
    )


def parse_hospital_list_text(text: str, default_hospital: str | None = None) -> list[ExtractedPerson]:
    """PDFs/tablas: fila numerada + hospital, nombre en MAYÚSCULAS, edad."""
    persons: list[ExtractedPerson] = []
    seen: set[str] = set()

    for match in _PIPE_TABLE_ROW_RE.finditer(text):
        hospital = match.group(2).strip()
        name = match.group(3).strip()
        age = match.group(4)
        person = _person_from_parts(name, hospital=hospital, age=age)
        if person and person.full_name.lower() not in seen:
            seen.add(person.full_name.lower())
            persons.append(person)

    if persons:
        return persons

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    current_hospital: str | None = default_hospital
    i = 0

    while i < len(lines):
        line = lines[i]

        if _JUNK_LINE_RE.search(line) or line.lower().startswith("registro maestro"):
            i += 1
            continue

        hospital_match = _HOSPITAL_ROW_RE.match(line)
        if hospital_match:
            current_hospital = hospital_match.group(2).strip()
            i += 1
            if i < len(lines) and _looks_like_caps_name(lines[i]):
                name_line = lines[i]
                i += 1
                age = None
                if i < len(lines) and _AGE_ONLY_RE.match(lines[i]):
                    age = re.sub(r"[^0-9]", "", lines[i]) or None
                    i += 1
                person = _person_from_parts(name_line, hospital=current_hospital, age=age)
                if person and person.full_name.lower() not in seen:
                    seen.add(person.full_name.lower())
                    persons.append(person)
                continue
            continue

        if _looks_like_caps_name(line):
            age = None
            j = i + 1
            if j < len(lines) and _AGE_ONLY_RE.match(lines[j]):
                age = re.sub(r"[^0-9]", "", lines[j]) or None
            person = _person_from_parts(line, hospital=current_hospital, age=age)
            if person and person.full_name.lower() not in seen:
                seen.add(person.full_name.lower())
                persons.append(person)

        i += 1

    return persons


def _looks_like_caps_name(line: str) -> bool:
    line = line.strip()
    if not _CAPS_NAME_RE.match(line):
        return False
    if not any(c.islower() for c in line):  # todo mayúsculas
        return is_plausible_person_name(line)
    return False


def parse_ocr_image_text(text: str, default_hospital: str | None = None) -> list[ExtractedPerson]:
    """Fotos WhatsApp: nombres en Title Case, a menudo tras línea Cama #N."""
    persons: list[ExtractedPerson] = []
    seen: set[str] = set()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for i, line in enumerate(lines):
        if _JUNK_LINE_RE.search(line):
            continue
        if re.match(r"^cama\s*#?\d", line, re.IGNORECASE):
            continue
        if _LOCATION_RE.search(line) or ":" in line and detect_state(line):
            continue
        if _AGE_ONLY_RE.match(line) or re.fullmatch(r"\d{6,}", line):
            continue

        candidate = line
        if _MERGED_NAME_RE.match(line):
            candidate = normalize_person_name(line)

        if _TITLE_NAME_RE.match(candidate) or (
            _MERGED_NAME_RE.match(line) and is_plausible_person_name(candidate)
        ):
            context = " | ".join(lines[max(0, i - 2) : min(len(lines), i + 3)])
            person = _person_from_parts(
                candidate,
                hospital=default_hospital,
                extra=context[:200] if "Cama" in context or "cama" in context else None,
            )
            if person and person.full_name.lower() not in seen:
                seen.add(person.full_name.lower())
                persons.append(person)

    return persons


def parse_spreadsheet_text(text: str, default_hospital: str | None = None) -> list[ExtractedPerson]:
    """Filas tipo: APELLIDO | NOMBRE | EDAD | CI | Hospital ..."""
    persons: list[ExtractedPerson] = []
    seen: set[str] = set()

    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 3:
            continue
        if parts[0].lower() in {"apellido", "nombre", "n°", "no"}:
            continue

        apellido, nombre = parts[0], parts[1]
        if not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{2,}", apellido) or not re.search(
            r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{2,}", nombre
        ):
            continue
        if apellido.lower() in _JUNK_WORDS or nombre.lower() in _JUNK_WORDS:
            continue

        full_name = normalize_person_name(f"{nombre} {apellido}")
        if not is_plausible_person_name(full_name):
            continue

        age = None
        hospital = default_hospital
        for part in parts[2:]:
            if re.fullmatch(r"\d{1,3}(?:\.0)?", part):
                age = str(int(float(part)))
            elif "hospital" in part.lower() or len(part) > 12:
                hospital = part

        person = _person_from_parts(full_name, hospital=hospital, age=age)
        if person and person.full_name.lower() not in seen:
            seen.add(person.full_name.lower())
            persons.append(person)

    return persons


def parse_noisy_ocr_fallback(text: str, default_hospital: str | None = None) -> list[ExtractedPerson]:
    """Último recurso: líneas cortas legibles en fotos manuscritas muy ruidosas."""
    persons: list[ExtractedPerson] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 6 or len(line) > 60:
            continue
        if _JUNK_LINE_RE.search(line) or re.search(r"[\u4e00-\u9fff]", line):
            continue
        words = line.split()
        if len(words) < 2 or len(words) > 4:
            continue
        if not all(re.search(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]{3,}", w) for w in words):
            continue
        if any(w.lower() in _JUNK_WORDS for w in words):
            continue

        candidate = normalize_person_name(line)
        if not is_plausible_person_name(candidate):
            # Relajar: al menos dos palabras con 4+ letras
            if not all(sum(c.isalpha() for c in w) >= 4 for w in words[:2]):
                continue
            if any(ch.isdigit() for ch in line):
                continue

        person = _person_from_parts(candidate, hospital=default_hospital, strict=False)
        if person and person.full_name.lower() not in seen:
            seen.add(person.full_name.lower())
            persons.append(person)
        if len(persons) >= 30:
            break

    return persons


def extract_persons_from_text(text: str, hospital_hint: str | None = None) -> list[ExtractedPerson]:
    """Pipeline unificado: tablas PDF → Excel → OCR legible → fallback ruidoso."""
    for parser in (
        lambda t: parse_hospital_list_text(t, hospital_hint),
        lambda t: parse_spreadsheet_text(t, hospital_hint),
        lambda t: parse_ocr_image_text(t, hospital_hint),
        lambda t: parse_noisy_ocr_fallback(t, hospital_hint),
    ):
        found = parser(text)
        if found:
            return found
    return []
