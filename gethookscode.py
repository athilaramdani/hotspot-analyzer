import os

def save_hooks_to_txt(folder="hooks", output_file="all_hooks_code.txt"):
    with open(output_file, "w", encoding="utf-8") as outfile:
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)

            # skip folder dan file non-py
            if os.path.isdir(filepath) or not filename.endswith(".py"):
                continue

            # tulis header nama file
            outfile.write("="*80 + "\n")
            outfile.write(f"📂 File: {filename}\n")
            outfile.write("="*80 + "\n\n")

            # tulis isi file
            with open(filepath, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
            
            outfile.write("\n\n")  # kasih jarak antar file

    print(f"✅ Semua file hooks berhasil digabung ke {output_file}")

if __name__ == "__main__":
    save_hooks_to_txt("hooks", "all_hooks_code.txt")
