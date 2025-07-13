# F:/projek dosen/prototype riset/hotspot-analyzer/main.py
import multiprocessing
from app.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()