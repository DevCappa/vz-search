EXTRACTION_PROMPT = """
Eres un asistente humanitario procesando listados de personas heridas o hospitalizadas
tras el sismo en Venezuela (2026).

Analiza el documento adjunto (puede ser foto escaneada, PDF, tabla o texto libre).
Extrae TODAS las personas mencionadas de forma coherente y normalizada.

Contexto del archivo:
- Ruta: {source_hint}
- Hospital probable: {hospital_hint}

Reglas:
1. Normaliza nombres completos en formato "Nombre Apellido" (capitalizado).
2. Si el hospital no aparece en el documento, usa el hospital probable del contexto.
3. Incluye estado/entidad si aparece (Miranda, Caracas, Zulia, etc.).
4. No inventes personas que no estén en el documento.
5. Si una fila está ilegible, omítela.
6. Responde SOLO con JSON válido, sin markdown ni texto extra.

Formato exacto:
{{
  "personas": [
    {{
      "full_name": "María González",
      "cedula": "V-12345678 o null",
      "age": "35 o null",
      "hospital": "nombre del hospital o null",
      "state": "estado venezolano o null",
      "condition": "herida leve/grave/estable/etc o null",
      "notes": "cualquier dato útil extra o null"
    }}
  ]
}}
"""
