#!/usr/bin/env python3
"""Provisioning-time CLI: generate an Ed25519 signing keypair, or sign a
device's identity into a `SignedDeviceLicense` (S1V2-02-027).

"Private Signing Keys nur im kontrollierten Provisioning/HQ-Kontext, nie
auf Kundenimage": this script lives at the repo root, not inside
`apps/customer-backend` - that app's Dockerfile only `COPY`s
`pyproject.toml` and `app/` from its own build context, so this script
(and any private key file passed to it) structurally never ends up on a
customer image. Run this with the customer-backend venv's Python (it
needs `pydantic`/`cryptography`, already dependencies there):

    apps/customer-backend/.venv312/bin/python3.12 scripts/sign_device_license.py generate-keypair
    apps/customer-backend/.venv312/bin/python3.12 scripts/sign_device_license.py sign \\
        --device-id <uuid> --serial-number SN-0001 --product-class pi \\
        --private-key-file private_key.b64 --output license.json
"""

import argparse
import base64
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "customer-backend"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from app.device_identity import DeviceIdentity, sign_device_identity  # noqa: E402
from app.product_class import ProductClass  # noqa: E402


def _generate_keypair() -> None:
    private_key = Ed25519PrivateKey.generate()
    print(f"private_key_base64={base64.b64encode(private_key.private_bytes_raw()).decode('ascii')}")
    print(f"public_key_base64={base64.b64encode(private_key.public_key().public_bytes_raw()).decode('ascii')}")
    print("\nKeep the private key in a controlled HQ/provisioning secret store only.")
    print("Ship only the public key to customer devices (SYSTEMONE_DEVICE_PUBLIC_KEY).")


def _sign(args: argparse.Namespace) -> None:
    private_key_b64 = Path(args.private_key_file).read_text(encoding="utf-8").strip()
    private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64))

    identity = DeviceIdentity(
        device_id=args.device_id,
        serial_number=args.serial_number,
        product_class=ProductClass(args.product_class),
        issued_at=datetime.now(UTC),
    )
    license = sign_device_identity(identity, private_key)
    Path(args.output).write_text(license.model_dump_json(), encoding="utf-8")
    print(f"Wrote signed device license to {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("generate-keypair", help="Generate a new Ed25519 signing keypair.")

    sign_parser = subparsers.add_parser("sign", help="Sign a device identity into a SignedDeviceLicense.")
    sign_parser.add_argument("--device-id", required=True)
    sign_parser.add_argument("--serial-number", required=True)
    sign_parser.add_argument("--product-class", required=True, choices=[c.value for c in ProductClass])
    sign_parser.add_argument("--private-key-file", required=True, help="File containing the base64-encoded private key.")
    sign_parser.add_argument("--output", required=True, help="Where to write the signed license JSON.")

    args = parser.parse_args()
    if args.command == "generate-keypair":
        _generate_keypair()
    elif args.command == "sign":
        _sign(args)


if __name__ == "__main__":
    main()
