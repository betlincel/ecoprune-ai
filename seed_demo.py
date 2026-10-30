"""Create a deterministic demo tree without overwriting existing files."""

from pathlib import Path

ROOT = Path(__file__).parent / "demo"
FILES = {
    "notlar_2025.txt": "EcoPrune demo: aynı içeriğin iki farklı adlı kopyası.\n",
    "notlar_kopya.txt": "EcoPrune demo: aynı içeriğin iki farklı adlı kopyası.\n",
    "kaynak/notlar.txt": "Aynı dosya adı, farklı içerik (kaynak).\n",
    "arsiv/notlar.txt": "Aynı dosya adı, farklı içerik (arşiv).\n",
    "benzersiz/okuma.txt": "Bu dosya yalnızca bir kez bulunur.\n",
    "benzersiz/veri.csv": "tur,deger\norman,42\n",
}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for relative, content in FILES.items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8", newline="") as stream:
                stream.write(content)
            print(f"Oluşturuldu: {path.relative_to(ROOT)}")
        except FileExistsError:
            print(f"Korundu (zaten var): {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
