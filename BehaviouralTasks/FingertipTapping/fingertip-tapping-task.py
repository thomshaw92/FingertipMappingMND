"""
fingertip-tapping.py
A PsychoPy experiment to measure fingertip tapping speed.

The script will display instructions to the participant, asking them to tap a specified finger on the space bar as fast as they can. This will be repeated for each finger three times, in a random order. 
Participants are instructed to wait for the finger instruction on the screen before beginning each trial.

At the end of each trial, the number of taps is saved, and an average is calculated for each finger.

The data will be written to a CSV file at a user-specified location.

This script was written for use with PsychoPy v2021.1.4.

Author: Tom Shaw t.shaw@uq.edu.au
Date: 2023 06 12
"""

from psychopy import visual, core, event, data, gui
import random
import csv
import os
from datetime import datetime
import wx

# Initialize a wx.App instance
app = wx.App(False)

# Information about the participant
info = {'Participant ID': '', 'Hand': ['Left', 'Right']}
infoDlg = gui.DlgFromDict(dictionary=info, title='Tapping Speed Experiment')
if infoDlg.OK:
    filename = gui.fileSaveDlg(prompt='Please choose the data file save location')
    if filename is not None:
        if not filename.endswith('.csv'):  # Ensure file has correct extension
            filename += '.csv'
    else:
        core.quit()
else:
    core.quit()

win = visual.Window([800,600], color='grey')

# Instructions
instructions = visual.TextStim(win, text='Tap the specified finger on the space bar as fast as you can when the countdown ends. You will be asked to do this for each finger three times, in a random order. Wait for the finger instruction on screen.', color='black')
instructions.draw()
win.flip()
core.wait(10)

# screen to prompt participant to press spacebar to begin
begin_prompt = visual.TextStim(win, text='Press spacebar to begin.', color='black')
begin_prompt.draw()
win.flip()

# Wait for spacebar press to begin
keys = event.waitKeys(keyList=['space'])
# Prepare for trial
ready_prompt = visual.TextStim(win, text='Please press the space bar when you are ready.', color='black')
# Finger names for display (use directly on screen)
finger_names = ['Thumb', 'Index', 'Middle', 'Ring', 'Fifth']
random.shuffle(finger_names)

trials = [1, 2, 3] * len(finger_names)
averages = {finger: [] for finger in finger_names}
results = []  # Initialize results list

for finger_name, trial_num in zip(finger_names*3, trials):
    # Instructions before trial
    finger_text = visual.TextStim(win, text=finger_name, color='black', pos=[0,0.5])
    finger_text.draw()
    win.flip()
    core.wait(3)

    # Wait for participant's readiness before each trial
    ready_prompt.draw()
    win.flip()
    event.waitKeys(keyList=['space'])

    # Countdown
    for i in range(3, 0, -1):
        countdown = visual.TextStim(win, text=str(i), color='black', pos=[0,0])
        countdown.draw()
        win.flip()
        core.wait(1)

    # Go signal
    go_text = visual.TextStim(win, text='GO!', color='black', pos=[0,0])
    go_text.draw()
    win.flip()

    # Trial start time
    start_time = core.getTime()

    # Reset keypress counter
    keypresses = 0

    # Trial
    while core.getTime() - start_time < 10:
        # Display finger name and Go signal throughout the trial
        finger_text.draw()
        go_text.draw()
        # Countdown timer
        countdown_timer = visual.TextStim(win, text=str(int(10 - (core.getTime() - start_time))), color='black', pos=[0,-0.5])
        countdown_timer.draw()
        win.flip()

        keys = event.getKeys()
        if 'space' in keys:
            keypresses += 1

    # Stop signal
    stop_text = visual.TextStim(win, text='STOP!', color='black', pos=[0,0])
    stop_text.draw()
    win.flip()
    core.wait(1)

    # Save the number of keypresses
    averages[finger_name].append(keypresses)
    results.append((finger_name, keypresses))  # Save results for each trial

# Calculate averages
averages = {finger_name: sum(averages[finger_name])/3 for finger_name in finger_names}

# Get current date and time
now = datetime.now()
date_time = now.strftime("%m/%d/%Y, %H:%M:%S")

# Write results to file
try:
    mode = 'a' if os.path.exists(filename) else 'w'
    with open(filename, mode, newline='') as f:
        writer = csv.writer(f)
        if mode == 'w':
            writer.writerow(['Participant ID', 'Hand', 'Date & Time', 'Finger', 'Taps', 'Average'])
        for f, t in results:
            writer.writerow([info['Participant ID'], info['Hand'], date_time, f, t, averages[f]])
        # Write averages for each finger to file
        writer.writerow([''] * 3 + ['Averages:'] + [''] * 2)
        for finger_name in finger_names:
            writer.writerow([''] * 4 + [finger_name, averages[finger_name]])
except IOError:
    print("Could not write to file. Please ensure the file is not open in another program and try again.")
    # Save data to a temporary file
    tmp_filename = os.path.join(os.path.dirname(filename), 'tmp_data.csv')
    with open(tmp_filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Participant ID', 'Hand', 'Date & Time', 'Finger', 'Taps', 'Average'])
        for f, t in results:
            writer.writerow([info['Participant ID'], info['Hand'], date_time, f, t, averages[f]])
        # Write averages for each finger to file
        writer.writerow([''] * 3 + ['Averages:'] + [''] * 2)
        for finger_name in finger_names:
            writer.writerow([''] * 4 + [finger_name, averages[finger_name]])
    print(f"Data was saved to a temporary file: {tmp_filename}")

# Display averages on screen
avg_text = "\n".join([f"{f}: {averages[f]}" for f in finger_names])
averages_disp = visual.TextStim(win, text=f'Averages:\n{avg_text}', color='black')
averages_disp.draw()
win.flip()
core.wait(10)

# End of the experiment
end_text = visual.TextStim(win, text='End of the experiment. Thank you!', color='black')
end_text.draw()
win.flip()
core.wait(5)
