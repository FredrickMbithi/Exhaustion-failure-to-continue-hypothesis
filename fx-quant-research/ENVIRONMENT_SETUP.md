# Environment Setup Instructions

## ✅ Quick Setup (Everything Already Done!)

Your virtual environment is already created and all packages are installed!

### To Use in VS Code Notebooks:

**Option 1: Let VS Code auto-detect (Recommended)**

1. **Reload VS Code window**: Press `Ctrl+Shift+P` → Type "Developer: Reload Window"
2. Open a notebook
3. VS Code should automatically detect and use `venv/bin/python`

**Option 2: Manual kernel selection**

1. Open a notebook (e.g., `02_stationarity_analysis.ipynb`)
2. Click the **kernel selector** in the top-right corner
3. Select **"Python (fx-quant-venv)"** from the list

**Option 3: Use kernel picker**

1. Press `Ctrl+Shift+P`
2. Type "Notebook: Select Notebook Kernel"
3. Choose **"Python (fx-quant-venv)"**

---

## 🔄 If You Need to Reinstall

Run the setup script:

```bash
cd "/home/ghost/Workspace/Projects/Exhausyion + filure to continue hupothesis/fx-quant-research"
./setup_env.sh
```

---

## 💻 Manual Commands

### Activate environment in terminal:

```bash
cd "/home/ghost/Workspace/Projects/Exhausyion + filure to continue hupothesis/fx-quant-research"
source ./activate_venv.sh
```

**Note**: Use `activate_venv.sh` instead of `venv/bin/activate` directly, as it handles the spaces in the directory path properly with your Kali shell prompt.

### Verify installation:

```bash
python -c "import pandas, numpy, scipy, statsmodels; print('✅ All packages work!')"
```

### List installed packages:

```bash
pip list
```

---

## 📦 Installed Packages

- pandas >= 2.0.0
- numpy >= 1.24.0
- scipy >= 1.10.0
- statsmodels >= 0.14.0
- matplotlib
- seaborn
- jupyter
- ipykernel
- And more...

---

## 🐛 Troubleshooting

### Notebook says "No module named 'pandas'"

- Your notebook is using the system Python, not the venv
- **Solution**: Follow "Option 1" above to reload VS Code

### Can't find the kernel

- **Solution**: Run `./setup_env.sh` to register the kernel again

### Terminal shows "basename: extra operand 'filure'"

- This occurs because your Kali shell prompt doesn't handle spaces in directory paths properly
- **Solution**: Use `source ./activate_venv.sh` instead of `source venv/bin/activate`
- The wrapper script disables the venv prompt modification to avoid conflicts

---

## 📍 Important Paths

- **Virtual environment**: `venv/`
- **Python executable**: `venv/bin/python`
- **Pip executable**: `venv/bin/pip`
- **Jupyter kernel**: `~/.local/share/jupyter/kernels/fx-quant-venv/`

---

**Current Status**: ✅ Environment ready to use!
