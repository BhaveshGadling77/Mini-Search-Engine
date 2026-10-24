# Building the Worklet 2 Python interface

Run these commands from the repository root. Activate the project's virtual
environment before installing `pybind11` and building the binding so that
`python3`, `python3-config`, and the `pybind11` module refer to the same Python
installation.

If the project virtual environment already exists, activate it:

```sh
source .venv/bin/activate
```

If it does not exist yet, create and activate it first:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Then install `pybind11` and build the interface:

```sh
python -m pip install pybind11
make pybind
```

The build creates the `wl2bridge` Python extension in `build/`. Keep the
virtual environment activated when importing or testing the extension. To
leave it, run `deactivate`.

for coding examples you can see the [Reference Codes](../../wl2/pybind_interface_testing/).