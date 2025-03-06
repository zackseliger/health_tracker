# Health Tracker

A health analytics platform that integrates data from Oura Ring API and Chronometer CSV files to analyze correlations between health metrics.

## Features

- Oura Ring API integration
- Chronometer CSV import
- Manual data entry
- Correlation analysis
- Data visualization

## Setup

1. Clone the repository
2. Install the package in development mode:

```bash
pip install -e .
```

3. Run the application:

```bash
python run.py
```

4. Open your browser and navigate to http://127.0.0.1:5000

## Requirements

- Python 3.6+
- Flask
- SQLAlchemy
- Pandas
- NumPy
- SciPy
- Requests

## Project Structure

- `app/`: Main application package
  - `models/`: Database models
  - `routes/`: Flask routes
  - `static/`: Static files (CSS, JS)
  - `templates/`: HTML templates
  - `utils/`: Utility classes for data import and analysis
- `run.py`: Application entry point
- `setup.py`: Package setup file 