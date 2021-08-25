  
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="massql",
    version="0.0.6",
    author="Mingxun Wang",
    author_email="mwang87@gmail.com",
    description="Mass spectrometry query language python implementation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mwang87/MassQueryLanguage",
    project_urls={
        "Bug Tracker": "https://github.com/mwang87/MassQueryLanguage/issues",
        "Documentation": "https://mwang87.github.io/MassQueryLanguage_Documentation/"
    },
    scripts=['msql_cmd.py'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=["massql"],
    install_requires=[
        "pymzml",
        "lark-parser",
        "pandas",
        "pyarrow",
        "ray",
        "tqdm",
        "py_expression_eval",
        "matchms",
        "pyteomics",
        "psims",
        "plotly",
        "kaleido",
        "pydot"
    ],
    python_requires=">=3.6",
    include_package_data=True
)
