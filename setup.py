from setuptools import setup, find_packages

setup(
    name="health_tracker",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "flask",
        "flask-sqlalchemy",
        "flask-migrate",
        "pandas",
        "numpy",
        "scipy",
        "requests",
    ],
) 