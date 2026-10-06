import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from apps.business_config.seed.actuarial_model import build_actuarial_model, COVERAGE_CODE_MAPPING
from apps.business_config.application.pricing import resolve_actuarial_coverage_premiums

model = build_actuarial_model()
print("COVERAGE_CODE_MAPPING keys:", list(COVERAGE_CODE_MAPPING.keys()))
print()

targets = {"Matriz_SAU": [12, 29, 46], "Matriz_SAG": [12, 29, 46]}
for pp in model["reference_pure_premiums"]:
    sheet, cell_ref = pp["source_cell"].split("!")
    row = int(cell_ref[1:])  # strip column letter (S) from S29 -> 29
    if sheet in targets and row in targets[sheet]:
        actuarial_code = pp["coverage_code"]
        mapped_bc = None
        for bc, acs in COVERAGE_CODE_MAPPING.items():
            if actuarial_code in acs:
                mapped_bc = bc
                break
        print(
            f"SOURCE={pp['source_cell']:25s} segment={pp['segment']:3s} plan={pp['plan']:20s} "
            f"actuarial_code={actuarial_code:15s} mapped_bc={mapped_bc}"
        )

        # Now try to resolve it and see what happens
        if mapped_bc:
            # Determine plan_code using command's _plan_code logic
            seg = pp["segment"]
            aplan = pp["plan"]
            mapping = {
                ("SAU", "Base"): "IND-BASE",
                ("SAU", "Conforto"): "IND-MEDIO",
                ("SAU", "Premium"): "IND-SUPERIOR",
                ("SAG", "Colaboradores"): "GRP-COLABORADORES",
                ("SAG", "Quadros Médios"): "GRP-QUADROS",
                ("SAG", "Administração"): "GRP-ADMINISTRACAO",
            }
            pcode = mapping.get((seg, aplan))
            print(f"  → plan_code={pcode}, testing resolve with age=30, sex=M")
            try:
                result = resolve_actuarial_coverage_premiums(
                    model=model,
                    plan_code=pcode,
                    coverages=[{"code": mapped_bc, "contracted": True}],
                    age=30,
                    sex_code="M",
                )
                for r in result:
                    print(f"     result code={r.get('code')}, pure_premium={r.get('pure_premium')}")
            except Exception as exc:
                print(f"     EXCEPTION: {type(exc).__name__}: {exc}")

print()
print("Todas as coverage codes únicas no modelo:")
codes = sorted(set(pp["coverage_code"] for pp in model["reference_pure_premiums"]))
for c in codes:
    print(f"  {c}")
