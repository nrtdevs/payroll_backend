$ErrorActionPreference = "Stop"

$python313 = "C:\Users\Lenovo\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $python313)) {
    throw "Python 3.13 not found at $python313"
}

$venvPython = Join-Path (Resolve-Path ".").Path ".venv313\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $python313 -m venv .venv313
}

& $venvPython -m pip install --upgrade pip "setuptools<81" wheel
& $venvPython -m pip install -r requirements.txt

# Install face_recognition without pulling source-built dlib on Windows.
& $venvPython -m pip install face-recognition==1.3.0 --no-deps

Write-Host "Windows dependencies installed successfully in .venv313"
Write-Host "Activate with: .\.venv313\Scripts\Activate.ps1"
