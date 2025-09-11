import os

# folder sumber dan file output
folder = "hooks"
output_file = "hasil_hooks.txt"

with open(output_file, "w", encoding="utf-8") as out:
    # loop semua file di folder hooks
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                out.write(f"==== {file}\n")
                with open(file_path, "r", encoding="utf-8") as f:
                    out.write(f.read())
                out.write("\n\n")  # kasih spasi antar file biar rapi

logging.info(f"  Semua kode Python dari folder '{folder}' udah dikumpulin ke '{output_file}'")
