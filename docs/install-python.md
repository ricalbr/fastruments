# Python Setup on Windows (with Spyder)

This tutorial provides a step-by-step guide to installing Python on a Windows system, creating a virtual environment, and configuring Spyder to use a custom Python interpreter.

---

## 1. Install Python

1. Download Python from the official website:
   https://www.python.org/downloads/windows/
2. Choose a stable Python 3 version (avoid very recent releases unless explicitly required).
3. Download the **Windows installer (64-bit)**.
4. Run the installer and **enable**:
   - [x] *Add python.exe to PATH*
   - (Optional) *Install for all users*
5. Complete the installation.

### Verify the Installation

Open **Command Prompt** or **PowerShell** and run:

```bash
python --version
pip --version
````

The `pip` tool is part of the Python standard distribution and is documented here:
[https://docs.python.org/3/installing/index.html](https://docs.python.org/3/installing/index.html)

---

## 2. Identify the Active Python Interpreter

Type the following command on the Command Prompt or PowerShell

```bash
where python
```

This command lists all Python executables found in the system `PATH`.

---

## 3. Create a Virtual Environment (Recommended)

Virtual environments isolate dependencies and prevent conflicts between projects and IDEs.

Python includes built-in support for virtual environments via the `venv` module:

[https://docs.python.org/3/library/venv.html](https://docs.python.org/3/library/venv.html)

### Create the Environment

```bash
python -m venv C:\venvs\myenv
```

### Activate the Environment

```bash
C:\venvs\myenv\Scripts\activate
```

### Update Core Tools

```bash
python -m pip install --upgrade pip setuptools wheel
```

---

## 4. Make the Environment Compatible with Spyder

Spyder does not automatically use external Python environments.

To enable compatibility, install the Spyder kernel inside the virtual environment:

```bash
pip install spyder-kernels
```

The kernel provides the communication layer between Spyder and the selected interpreter.

---

## 5. Configure Spyder to Use the Virtual Environment

1. Launch **Spyder**.
2. Go to:
   ```
   Tools → Preferences → Python Interpreter
   ```
3. Select **Use the following Python interpreter**.
4. Set the interpreter path to:
   ```
   C:\venvs\myenv\Scripts\python.exe
   ```
5. Apply the changes.
6. Restart the Spyder kernel when prompted.

Spyder will now execute code using the selected environment.

---

## 6. Best Practices

* Avoid installing packages in the system-wide Python.
* Keep Python and dependency versions documented.
* Always verify the active interpreter when working with multiple installations.
* Prefer standard library modules when possible to reduce external dependencies.

---

## Troubleshooting

* If Spyder cannot start the kernel, check the installed `spyder-kernels` version.
* If the wrong Python interpreter is used, inspect:
  ```bash
  where python
  ```
* Restart Spyder after changing the interpreter.

