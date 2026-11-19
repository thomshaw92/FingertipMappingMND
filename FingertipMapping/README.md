 300922 – Summary of old finger mapping protocol from Alex for replicating & changes



Alex old script details

-	Freqs = 5 20 100

-	Runs = 3
o	Repeat the 5 cycles 3 times
o	Not going to do this anymore – will just set up as a set of 5 cycles and run again each time we want to start
-	Cycles = 5
o	Sweep the fingers 5 times
-	Freq changes per digit = 4
-	Duration_freq = 1 TR
o	Old = 1920
-	Duration_finger = 4 * TR
o	Old = 7680

-	Before period = stimulation duration (4 * TR) * number of digits (4)
o	Old = 7860 * 4 = 30,720
-	After period = same

-	Duration_run = before period + (cycles * duration_finger * num_fingers) + after period
o	Old 	= 30,720 + (5 * 7680 * 4) + 30,720
o	 	= 30,720 + 153,600 + 30,720
o	 	= 215,040
-	Duration_total = duration_run * runs
o	Old = 215,040 * 3 = 645,120

-	TRs_total = 336



New script details
-	Phase encoded design: Exactly as above, except just one run
o	Thus, duration of run above in old script (215, 040ms) or 215.04 secs = duration of total in new script
	3.584 mins
o	TRs = 112 (i.e., 336/3)


30/09/22 – Have checked new script (FingerMapping_newStims_300922) and the phase encoded version matches these values for TR and timing exactly when using same fingers, freq changes per digit etc.

-	Now have changed so it runs stimulation on 5 not 4 fingers
o	Now duration of run/ total duration = 38.4 + 192 + 38.4
o	Run time = 268.801/ 60
	4.48 mins
o	TRs = 140


Sanne
-	10 sec stimulation/ finger
-	5 fingers = 50 sec/ cycle
-	7 cycles = 50 * 7 = 350 seconds = 5.833 mins
-	Run time = 6min 4 sec
o	So dead time must have been about 6.2 seconds at start and end

-	2 x forward + 2 x backward runs = 4 runs
-	4 runs x 7 cycles = 28 cycles
-	Stimulation time = 5.833 mins * 4 = 23.33 mins

Ours
-	7.68 stimulation/ finger
-	5 fingers = 38.4 sec/ cycle
-	5 cycles = 38.4 * 5 = 192 seconds = 3.2 mins
-	Run lasts = 4 min 48 sec
o	Dead time = stimulation duration (7.68) * num_digits (5) = 38.4 seconds at start and end, bit long, might cut to more like 15

-	2 x forward + 2 x backward runs = 4 runs
-	4 runs x 5 cycles = 20 cycles
-	Stimulation time = 3.2 mins * 4 = 12.8 mins
o	NOT LONG ENOUGH PROB

-	3 x forward + 3 x backward = 6 runs
-	6 runs x 5 cycles = 30 cycles
-	Stimulation time = 3.2 mins * 6 = 19.2 mins
o	Still less, might be less hassle to increase number of cycles instead of number of runs

-	With shorter deadTR time (see below), one run now = 192 seconds + 19.2 * 2 = 230.4 seconds/ 60 = 3.84 mins

-	Changed to 7 not 5 cycles
-	7.68 seconds stimulation/ finger
-	5 fingers = 38.4 sec/ cycle
-	7 cycles = 38.4 * 7 = 268.8 seconds = 4.48 mins
o	We have 1 min 35 sec less stimulation/ run than Sanne in phase encoded design
-	Run time = 5 min 12 sec
o	268.8 + (19.2*2) = 307.2

-	2 x forward + 2 x backward runs = 4 runs
-	4 runs x 7 cycles = 28 cycles
-	Stimulation time = 4.48 mins x 4 = 17.92 mins
o	5 min 41 sec less stimulation than Sanne

## BUT Tom is changing the TR – which will reduce the stimulation time per finger, so will need more freq changes per finger to increase stimulation time to closer to 10 seconds per finger

-	TR = 1.780
-	Freq changes/ finger, changed from 4 to 5
-	8.9 seconds stimulation/ finger
-	5 fingers = 44.5 seconds
-	7 cycles = 311.5 seconds
o	5.19 mins stimulation time
	38.5 seconds stimulation time less than sanne
-	Run time = 347.1 seconds = 5.78 mins
o	Dead time = (10 * TR ) * 2 = 17.8 x 2 = 35.6


CHANGES TO ALEX’S SCRIPT
-	Now shortened dead TRs at start and end to half what it was before (see above)
o	dur_deadTRs = (dur_fing * num_tactors)/2 = 19.2 for 5 fingers which is plenty I think but check with Alex
-	Also new script allows phase forward and backward orders
-	Also changed so can do phase encoded or blocked design
-	Have made allowances in the script so you can change how it stimulates the finger – the nature of each pulse (see images below)
o	Currently set to use pulsetype = 2 (see below) – note using this method effective freq = 5, 20 83 not 5, 20, 100 as gets entered at the start
	Have made it so matlab calcs these actual freqs and saves them, might want to consider relabelling timing files with these actual freq values, though may not matter as we likely not using the timing files
-	General notes
o	Because the freqs are randomised (with a no repeating within a finger rule) you don’t end up with exactly the same number of freqs presented overall, it’s about the same, but varies randomly and not enough trials so it ends up evening out perfectly. Also, not same number of freqs/ finger for same reason. We don’t really care about this as freqs are just for adaptation reasons though so is ok
	E.g., in this set I randomly got 39 trials of 5Hz, 30 of 20Hz and 31 of 100 (i.e., 83) Hz
## At line ~368, when at the scanner computer, I put a lock on the keyboard. This is so scanner triggers don’t show up in the matlab command window. But also means if you crash early it doesn’t get to the line where it opens the keyboard back up again and it might seem like matlab is frozen.
### If this happens, just go to the script line ~373 and highlight the line that says ‘ListenChar(1)’ right click on it and press Evaluate to reopen keyboard



Stimulation differences – pulsetype variable

Pulsetype = 1
-	Sine wave of desired frequency
If using pulsetype 1, need to set whether you want the variable pulsetype_removeneg to 1 (leave as generates normally) or 2 (remove negative values). See images below 
-	Reason to use = if you want to make sure you are getting the exact right number of hertz as specified in freq
o	Arguments against = I think one pulse feels a bit like two pulses with the MR stims, as it pulses up and down. This needs to be verified by other people/ accelerometer though
o	This issue may be improved by removing the negative values, thus, recommend using this setting with this pulse type


Pulsetype = 1, pulsetype_removeneg = 1, freq = 5
 


Pulsetype = 1, pulsetype_removeneg = 1, freq = 5
 


Pulsetype = 2
-	Single very short square wave pulse of a constant duration (100 vector units at Fs = 48000 = ~.002 seconds)
-	Reason to use = 1 pulse definitely feels like one single clean pulse to me. My preferred kind of stimulation over whatever pulsetype =1 makes the tactors do.
o	However, you don’t cleanly get the hertz of the freq you put in.
o	Can easily calc how many pulses you get in a second and report this as your effective Hz though.
	With freq = 5, you get 5 stimuli/ sec, so 5 hz as you want
	With freq = 20, you get 20 stimuli/ sec, also all good
	With freq = 100, you get 83 stimuli/ sec, because you would need a shorter pulse than 100 vector units to fit all 100 in
•	But with simple finger mapping we are just trying to avoid adaptation by using different freqs, we don’t care about the precise Hz, so I think its fine and prefer this method


Pulsetype = 2, freq = 5
 

Understanding the ‘Timing’ matrix in phase encoded design
Row 1 = finger stimulated
Row 2 = frequency change
Row 3 = freq
Row 4 = timing in TRs for that trial
Row 5 = timing in secs ‘’
Row 6 = timing in TRs – cumulative
Row 7 = timing in secs - cumulative
 

Blocked design
-	Same details as phase encoded, just randomised finger order i.e., length of stimulation is the same, freq changes on each finger is same
-	And, rest in between each finger
-	Run/ total duration = 460.80 secs
o	7.68 mins
o	(3.22 longer than phase encoded design per run)
-	TRs = 240 (100 more than phase encoded)


Sanne
-	8 sec stimulation/ finger
-	5 fingers + rest block = 6 conditions
o	Does not say how long rest is but suggests it is same as movement condition
o	Says counterbalanced order for all conditions, so guess they just had rest in there once per cycle, not between every finger as we did
-	5 cycles
-	8 x 6 x 5 = 240 seconds = 4 min
-	Run time = 4 min 14 seconds
o	Dead time was therefore, 7 seconds at the start and end

-	4 runs x 4 min stimulation = 16 min stimulation time


Ours
-	7.68 sec stimulation/ finger
-	5 fingers + rest block = 6 conditions
o	Rest is as long as movement
o	BUT, I had rest in between each finger condition, so this doubled the time
o	Might want to fix this to make same as Sanne
-	5 cycles
-	(7.68 x 2) x 5 x 5 = 384 seconds = 6.4 mins
o	Actual stimulation time = 7.68 x 5 x 5 = 192 sec/ 60 = 3.2 mins, i.e., half
-	Run time = 7 min 68 seconds
o	Dead time is 38.4 seconds at start and end

-	4 runs x 3.2 mins stimulation time = 12.8 mins stimulation time


Changed so rest only happens once per cycle
Also changed TR and number of cycles (see info in phase encoded design above)
-	8.9 seconds stimulation/ finger
-	5 fingers + rest = 6 conditions
-	7 cycles
-	8.9 x 6 x 7 = 373.8 seconds = 6.23 mins
o	2.18 mins more stimulation time than Sanne
-	Run time = 409.4 seconds = 6.82 mins
o	Dead time = 17.8 * 2
o	About 2.68 mins longer run time per run

-	4 runs x 6.3 mins stimulation time = 25 mins stimulation time
o	9 mins more stimulation time than Sanne
-	4 runs x 6.8 mins experiment time = 27.2 mins duration

Understanding the ‘Timing’ matrix in phase encoded design
Rows as above
 


Questions about blocked design
-	Rest is the same duration as the length of stimulation of a single finger – this ok?
o	i.e., finger gets stimulated for 7.68 secs, then rest for 7.68 secs
	During the finger stim period there are 4 freq changes on that one finger



% % To do - Ash/ Tom
1.	TURN TACTORS ON (now playing in debugging mode, just visuals that were added to check it is working and no stims) (line 91, change to 1 from 0)
2.	Work out with Alex/ the tactors what pulse type to use - call me about this so we can chat about it
3.	Change things for scanner PC - homedir (116)
4.	Work out what amp is good for good level of feeling of stims in the scanner - will need to coordinate with computer master volume controls
5.	(if needed) Edit TR
6.	(if needed) If changing tactor order - check this works with the make_sound script - could not check as tactors were all blown when writing this
 
% % May be needed (but hopefully not)
1.	If changing number of freqs (not 3) - will need to change the post experiment thing where it creates the timing file, set up to only do 3 now




SANNE full methods

“The travelling wave paradigm involved individuated finger movements in a set sequence. Each 10 s finger movement block was immediately followed by a movement block of a neighbouring finger. The forward sequence cycled through the fingers: thumb-index-middle-ring-little. To account for order-related biases due to the set movement cycle and sluggish haemodynamic response, we also collected data using a backward sequence: the backward sequence cycled through the movements in a reverse of the forward sequence: little-ring-middle-index-thumb fingers. The forward and backward sequences were employed in separate runs. A run lasted 6 min and 4 s, during which a sequence was repeated seven times. The forward and backward runs were repeated twice, with a total duration of 24 min and 16 s. 

The blocked design consisted of six conditions: movement conditions for each of the five fingers and a rest condition. Finger movement instructions were as described above, and the word ‘Rest’ indicated the rest condition. A movement block lasted 8 s, and each condition was repeated five times per run in a counterbalanced order. Each run comprised a different block order and had a duration of 4 min and 14 s. We acquired four runs, with a total duration of 16 min and 56 s. ”
