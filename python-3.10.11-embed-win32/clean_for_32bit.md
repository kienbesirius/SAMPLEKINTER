# Xoá “đúng chỗ” các gói đang là x64 (khuyên làm theo thứ tự)
Remove-Item -Recurse -Force .\Lib\site-packages\pandas
Remove-Item -Recurse -Force .\Lib\site-packages\pandas.libs
Remove-Item -Recurse -Force .\Lib\site-packages\pandas-*.dist-info

Remove-Item -Recurse -Force .\Lib\site-packages\PIL
Remove-Item -Recurse -Force .\Lib\site-packages\pillow-*.dist-info

Remove-Item -Recurse -Force .\Lib\site-packages\charset_normalizer
Remove-Item -Recurse -Force .\Lib\site-packages\charset_normalizer-*.dist-info

Remove-Item -Recurse -Force .\Lib\site-packages\tkinterdnd2\tkdnd\win-x64
Remove-Item -Recurse -Force .\Lib\site-packages\pandas -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\Lib\site-packages\pandas.libs -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\Lib\site-packages\pandas-*.dist-info -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\Lib\site-packages\PIL -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\Lib\site-packages\pillow-*.dist-info -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\Lib\site-packages\charset_normalizer -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\Lib\site-packages\charset_normalizer-*.dist-info -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\Lib\site-packages\tkinterdnd2\tkdnd\win-x64 -ErrorAction SilentlyContinue

Get-ChildItem .\Lib\site-packages -Recurse -Include *.pyd,*.dll |
  ForEach-Object { $_.FullName }

Remove-Item -Recurse -Force .\Lib\site-packages\tkinterdnd2\tkdnd\win-arm64 -ErrorAction SilentlyContinue


.\python.exe -c "import numpy as np; print('numpy', np.__version__); print(np.arange(3))"
.\python.exe -c "import requests; print('requests ok')"
.\python.exe -c "from PIL import Image; print('pillow ok')"
.\python.exe -c "import pandas as pd; print('pandas', pd.__version__)"

# Cài lại bản 32-bit (x86) bằng pip và ép “binary wheel”
.\python.exe -m pip install --no-cache-dir --only-binary=:all: charset-normalizer
.\python.exe -c "import requests; print('requests ok')"

.\python.exe -m pip install --no-cache-dir --only-binary=:all: pillow
.\python.exe -c "from PIL import Image; print('pillow ok', Image.__version__)"

.\python.exe -m pip install --no-cache-dir --only-binary=:all: "pandas==2.0.3"
.\python.exe -c "import pandas as pd; import numpy as np; print('pandas', pd.__version__, 'numpy', np.__version__)"

.\python.exe check_32bit_compat.py "C:\Users\koona\Videos\python-3.10.11-embed-win32\Lib\site-packages"

# Recheck 
.\python.exe check_32bit_compat.py "C:\Users\koona\Videos\python-3.10.11-embed-win32\Lib\site-packages"
