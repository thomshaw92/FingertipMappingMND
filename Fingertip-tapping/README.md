# Fingertip Tapping Experiment Setup Guide

This guide will walk you through how to setup and run the fingertip tapping experiment using PsychoPy on Windows.

## Prerequisites

Ensure that you have the following software installed:

1. [Miniconda](https://docs.conda.io/en/latest/miniconda.html)

## Setup

1. Download and install Miniconda from the link above. Please select the Python 3.x version and Windows 64-bit version. Make sure to check "Add Miniconda to my PATH environment variable" during installation.
2. Open Command Prompt.
3. Set up a new conda environment using the following command: `conda create -n psychopy python=3.6`.
4. Activate the environment using the command: `conda activate psychopy`.
5. Install PsychoPy in the environment using the command: `pip install psychopy`.
6. Download the fingertip-tapping.py script and save it in a convenient location.

## Running the experiment

1. Open Command Prompt.
2. Activate the PsychoPy environment using the command: `conda activate psychopy`.
3. Navigate to the directory where you saved the fingertip-tapping.py script using the `cd` command. For example, if you saved the script in a folder called 'Experiments' on your desktop, you would use the command: `cd Desktop\Experiments`.
4. Run the script using the command: `python fingertip-tapping.py`.

Follow the on-screen instructions to carry out the experiment.

## Data

The script will save the experiment data in a CSV file at a location you specify. Each row in the file represents a trial, with columns for participant ID, hand, date & time, finger, taps, and average taps. At the end of the data for each participant, the averages for each finger are written to the CSV file. 

### NB - the data.csv file must already exist 
You can create one by making a new text file in the location and naming it data.csv

If there is an error writing to the specified file (for example, if the file is open in another program), the data will be saved to a temporary file in the same location.

## Troubleshooting

If you encounter errors, make sure that:

- Miniconda is installed and added to your PATH environment variable.
- The PsychoPy environment is activated before running the script.
- The script is run using Python from the PsychoPy environment.
- The file you specify to save the data to is not open in another program.
