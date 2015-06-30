`build_from_pypi` automatically builds Conda packages from PyPI. To build top
`n` sorted by download count packages run:

```
python build_from_pypi.py -n 100 --recipe --build --pipbuild
```

This will first create recipes using `conda-skeleton` for the top 100 packages,
then it uses `conda-build` to create Conda package out of those recipe. If this
fails `build_from_pypi` will try to use the `pipbuild` process.

* * *

This repository also comes with a script to create a "report" to keep track of
the "status" of the package. To generate report use:

```
python compile_report.py
```

This generates `markdown` files `main_report`, `recipe_report`, `build_report`
and `pipbuild_report` and corresponding html renderings.
