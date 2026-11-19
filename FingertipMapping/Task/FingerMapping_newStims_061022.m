% % To do - Ash/ Tom
% TURN TACTORS ON (now playing in debugging mode, just visuals that were added to check it is working and no stims) (line 91, change to 1 from 0)
% Work out with Alex/ the tactors what pulse type to use - call me about this so we can chat about it
% Change things for scanner PC - homedir (116)
% Work out what amp is good for good level of feeling of stims in the scanner - will need to coordinate with computer master volume controls
% (if needed) Edit TR
% (if needed) If changing tactor order - check this works with the make_sound script - could not check as tactors were all blown when writing this

% % May be needed (but hopefully not)
% If changing number of freqs (not 3) - will need to change the post experiment thing where it creates the timing file, set up to only do 3 now


%% Clean up

% Matlab cleaning things5
sca;
close all;
clearvars;


%% Important tactor and sound card settings

% Remind to set comp vol and amp vol
input(sprintf('Set comp vol to 50, turn knobs on amp to full'));

% Remind to check tactor orders
input(sprintf('Check tactor orders before starting'));
clear ans

% Set which computer: 0 = home mac, 1 = scanner PC
scannerPC = 1;

% Set number of channels - WONT EVER CHANGE FROM 6
num_chans = 6;

% Set number of tactors on
num_tactors = 5;

% Set whether running 1 = phase encoded design (e.g., 1, 2, 3, 4, 5) or 2 = blocked design (random with rests)
phaseorblocked = input('1 = Phase encoded design; 2 = Blocked design: ', 's');
phaseorblocked = str2double(phaseorblocked);
% phaseorblocked = 1;

% (where relevant) Set whether running 1 = forward e.g., 1,2,3,4,5 or 2 = backward e.g., 5,4,3,2,1
if phaseorblocked == 1
    % 280723 HDJ edit - Not using backward, set to always forward
    forwardback = 1;
    % forwardback = input('1 = Phase forward (1,2,3,4,5); 2 = Phase backward (5,4,3,2,1): ', 's');
    % forwardback = str2double(forwardback);
    % forwardback = 1;
else
end

% Pulse type is regular sine wave (1) or spaced pulse (2) version (spaced pulse is a short single pulse (pos values only) delivered at different ISIs to get the frequency - this is to deal with issue of the lower frequencies not feeling very intense)
pulsetype = 2;

% If using pulse type 1 (sine) - do you want to 1 = leave as generated, 2 = remove values under 0
if pulsetype == 1
    % Set to remove negative values so stimulator does not do downward pulse
    pulsetype_removeneg = 2;
else
end

% Pre-set order for tactors (need to put in a weird order for them to play 1-5?)
tacorder_yn = 0; % pre-set order needed

% Get order if needed
if tacorder_yn == 0
    
    % no pre-set order
    tacorder = 1:num_chans;
    
else
    
    % needs a pre-set order - enter manually
    if num_tactors == 4
        % ADD WHEN WORKED THIS OUT
    elseif num_tactors == 5
        tacorder = [1, 2, 5, 3, 4, 6]; % 6 does not do anything
        % tacorder = [1, 2, 4, 5, 3, 6]; % 6 does not do anything
        % tacorder = [1, 2, 5, 6, 3, 4]; % 4 does not do anything - original with plugged chans 1-5
    else
    end
    
end

% Find out which should be zero
taczeros = tacorder(1, num_tactors+1:end);


%% General settings and start up things

% Turn things on = 1, or off = 0
psychvis = 1;
tactorsOn = 1;

% turn off sci notation
format long g


%% General stimulation timing details

% Set TR
TR = 1.920;
% TR = 1.920; % Ash's old TR was 1.992 (NOT USING)
% TR = 1; % for debugging - for working out how many stimuli/ second with different pulse types

% Number of times you sweep across the fingers
num_cycles = 7;

% Number of times you change freq in a finger stimulation period
num_freqChanges = 5;

% Duration of stimulation for each frequency
dur_freq = TR;

% Duration of stimulation for a finger
dur_fing = num_freqChanges * dur_freq;

% Number of TRs before stimulation starts (at start AND end of block)
dur_deadTRs = TR*10;


%% Make sound base parts

% Common sound settings for all sounds
amp = 7; % May need to work out what is ideal
Fs = 48000; % need to use this for PC
phase = 0; % phase shift - we aren't using this so set to 0

% Set freqs
freqs = [5 20 100]; % in Hz

% Make sound
make_sound_140922


%% Create timing matrix

% Get row numbers for different vars
row_fing = 1; row_freqChange = 2; row_freq = 3; row_realTRtime = 4; row_realtime = 5; row_realTRtime_cum = 6; row_realtime_cum = 7;
row_tictoctime = 8; row_tictoctime_cum = 9;

% Initialise timing matrix - the extra 2 are for the dead TRs (start & finish)
if phaseorblocked == 1
    % Phase encoded
    timings = zeros(9, (num_cycles*num_tactors*num_freqChanges) + 2);
else
    % Blocked - needs more spaces for rests (1 per finger/ cycle)
    timings = zeros(9, (num_cycles*(num_tactors+1)*num_freqChanges) + 2);
end

% Start freq counter
cfr = 0;

% % Start fing counter
% if phase encoded, start depends on forward or backward phase
% if blocked, generate vector of finger order (based on number of cycles), shuffled and pick the first one as cfi
if phaseorblocked == 1
    if forwardback == 1
        cfi = 1;
    else
        cfi = num_tactors;
    end
else
    % Create blank matrix for finger order
    fing_order = [];
    
    % Generate finger order & shuffle - make sure no repeats of same finger twice in a row
    for fr = 1:num_cycles
        
        % Generate and shuffle
        fing_order_new = Shuffle(0:num_tactors);
        
        % Check for repeat
        if fr == 1
            fing_order = fing_order_new;
        else
            % Set finished counter
            finished_fing = 0;
            
            % Loop to keep shuffling until you get a non-match
            while finished_fing == 0
                
                if fing_order(1,end) ~= fing_order_new(1,1)
                    % No match - can stop
                    finished_fing = 1;
                    
                    % Add data
                    fing_order = [fing_order, fing_order_new];
                    
                else
                    % Shuffle again
                    fing_order_new = Shuffle(fing_order_new);
                end
            end
        end
        clear fing_order_new

    end
    
    % Get first finger as cfi
    cfi = fing_order(1);
    
    % Start finger counter
    cf = 1;
end


% Loop to add in desired times  
for t = 1:size(timings,2)
        
    if t == 1
        % Put dead TRs
        timings(row_realTRtime,t) = dur_deadTRs/ TR;
    elseif t == size(timings,2)
        % Put dead TRs
        timings(row_realTRtime,t) = dur_deadTRs/ TR;
    else 
            % Add to freq counter
            cfr = cfr+1;

            % Add freq number into timing mat
            timings(row_freqChange,t) = cfr;

            % Add fing number to timing mat
            timings(row_fing,t) = cfi;

            % Determine what freq for stimulation
            if cfr == 1
                % Randomly shuffle freqs
                freq_rands = freqs(randperm(length(freqs)));

                % Put the first one in a vector
                freq_stim(1, cfr) = freq_rands(1,1);

            else
                % Randomly shuffle freqs
                freq_rands = freqs(randperm(length(freqs)));

                % Check if the first freq is the one used last time
                if freq_rands(1,1) == freq_stim(1, cfr-1)
                    % Current freq IS the same as last one used - remove it
                    freq_rands = freq_rands(2:end);

                else
                end

                % Add freq to matrix
                freq_stim(1, cfr) = freq_rands(1,1);
            end
            clear freq_rands

            % Put freq value in timing matrix (if its not a rest block)
            if cfi ~= 0
                timings(row_freq, t) = freq_stim(1,cfr);
            else
            end

            % Determine whether to add to fing counter
            if cfr == num_freqChanges

                % Clear freq_stim
                clear freq_stim

                % % Phase encoded design
                if phaseorblocked == 1

                    % Check we have done a whole cycle of fingers
                    if forwardback == 1
                        if cfi == num_tactors
                            finishedcycle = 1;
                        else
                            finishedcycle = 0;
                        end
                    else
                        if cfi == 1
                            finishedcycle = 1;
                        else
                            finishedcycle = 0;
                        end
                    end

                    % Pertform action based on whether finished cycle or not
                    if finishedcycle == 1
                        % Reset back to initial finger
                        if forwardback == 1
                            cfi = 1;
                        else
                            cfi = num_tactors;
                        end
                    else
                        % Add/ subtract to fing counter - depends on forward or back phase
                        if forwardback == 1
                            cfi = cfi + 1;
                        else
                            cfi = cfi - 1;
                        end
                    end
                    clear finishedcycle

                else
                    % % Blocked design

                    % If you got to the end of the finger trials - don't bother trying to add to the finger counter etc.
                    if cf ~= size(fing_order,2)
                        % Add to finger counter
                        cf = cf + 1;

                        % Get next finger based on finger counter
                        cfi = fing_order(cf);
                    else
                    end

                % end if phaseorblocked    
                end

                % Reset cfr to 0
                cfr = 0;
            else
            end

            % Put stimulus times in
            timings(row_realTRtime,t) = dur_freq/ TR;
    end
        
    
    % Work out time in secs for this segment only
    timings(row_realtime, t) = timings(row_realTRtime,t) * TR;

    % Add TRs cumulatively
    timings(row_realTRtime_cum,t) = sum(timings(row_realTRtime,:));

    % Work out time in secs for timing cumulatively
    timings(row_realtime_cum,t) = timings(row_realTRtime_cum,t) * TR;
    
end

clear t
clear cfi cfr cf

% % For debugging - check how many of each finger/ stim etc
% which_check = row_freq;
% values = unique(timings(which_check, :))
% counts = histc(timings(which_check, :), values)
% clear which_check values counts

% Get number of TRs
TRs = sum(timings(row_realTRtime,:));


%% Get subj & filename details

% Input participant details
% p_init = 'h'; subnum = 1; % JUST FOR PILOTING
% run_num = 1;
p_init = input('Participant Intitials: ', 's');
subnum = input('SUBJECT Number: ');
run_num = input('Run Number (0 for training): ');

% date tag
clockdat = clock;
clockdat = clockdat(1:5);
datetag = sprintf('%d_%d_%d_%d_%d',clockdat); 
clear clockdat

if subnum < 10
    subcode = ['P00' num2str(subnum)];
else
    subcode = ['P0' num2str(subnum)];
end

% Generate filename
filename = ['fingermaps_', subcode, '_', p_init, '_run', num2str(run_num)];

% Add phase or blocked to filename
if phaseorblocked == 1
    filename = [filename, '_phase'];
else
    filename = [filename, '_blocked'];
end

% If phase - Add foward or back to filename
if phaseorblocked == 1
    if forwardback == 1
        filename = [filename, '_forward'];
    else
        filename = [filename, '_backward'];
    end
else
end

% Add datetag
filename = [filename, '_', datetag];

% Pop filename on screen so experimenter can check participant dets and cancel out if details are wrong
input(sprintf('Check participant dets: %s - exit if incorrect', filename));
clear ans


%% Make dir for that participant in Data dir if it doesn't exist already

% Set home directory
if scannerPC == 0
    homedir = '/Users/uqhdemp1/Documents/2022/Analysis & fMRI General/Fingertip maps/Script_new_stims'; % office mac
else
    homedir = 'C:\Users\meduser\Documents\FingertipMappingMND\Fingertip_mapping\Script'; % ADD FOR STIMS PC
end

% Set data directory
if scannerPC == 0
    % Set to individual sub folder
    datadir = [homedir, '\Data\', subcode, '_', p_init,'\'];
    
    % Make individual sub name folder if it's not there already
    if ~exist(datadir, 'dir')
    mkdir(datadir);
    end

else
    % Set to data general folder - as cannot make new directories in matlab on scanner PC
    datadir = [homedir, '\Data\'];
end
clear homedir


%% Initialise Psychtoolbox things

% % Audio
if tactorsOn == 1
    % Make sure any old audio stuff is closed
    PsychPortAudio('Close');

    % Initialises sound driver...the 1 pushes for low latency
    InitializePsychSound(1);

    % Initialise two sound buffers for the two sounds
    pahandle = PsychPortAudio('Open', [], [], 2, Fs, num_chans, 0); % for the first played sound

    % % play test sound - load into buffer then play then wait
    PsychPortAudio('FillBuffer', pahandle, testall); PsychPortAudio('Start', pahandle, 1, 0); WaitSecs(1);
else
end
clear testall ans

% % Keyboard - note some key restrictions added later below
% improve portability of your code across operating systems 
KbName('UnifyKeyNames');

% Suppress output from keyboard - if at the scanner
if scannerPC == 1
    ListenChar(2);
else
end

% Reallow if needed - leave commented out ALWAYS
% ListenChar(1);

% Turn off any previous keyboard restrictions for keyboard check - in case were left on (as can restrict trigger)
RestrictKeysForKbCheck([]);


% % Visuals
if psychvis == 1
    % Initialise some set up parameters
    PsychDefaultSetup(2);

    %Choosing the display
    screens=Screen('Screens'); screenNumber=max(screens); clear screens

    %Open Screen
%     [window, windowRect] = PsychImaging('OpenWindow', screenNumber, 255/4); %255/2 CHANGED TO 255/4
    backgroundCol = [128 128 128];
    [window, windowRect]=Screen('OpenWindow', screenNumber, backgroundCol);
    % [window, windowRect]=Screen('OpenWindow', screenNumber,[], [10 20 600 300]); % small debugging window

    % Set screen parameters
    Screen('TextSize', window, 40);

    % Set up alpha-blending for smooth (anti-aliased) lines --> fixation cross below wont run without it
    Screen('BlendFunction', window, 'GL_SRC_ALPHA', 'GL_ONE_MINUS_SRC_ALPHA');

    % Set things up for fixation cross
    [xCentre, yCentre] = RectCenter(windowRect); fixCrossDimPix = 40; xCoords = [-fixCrossDimPix fixCrossDimPix 0 0]; yCoords = [0 0 -fixCrossDimPix fixCrossDimPix]; allCoords = [xCoords; yCoords]; clear fixCrossDimPix xCoords yCoords; lineWidthPix = 4;

    clear ans
else
end


%% Present general instructions on screen

if psychvis == 1
    % Instruction
    DrawFormattedText(window, sprintf('Watch the fixation cross through the whole experiment\n\n and do not move (please)'), 'center', 'center', [0 0 0]);
    Screen('Flip', window);
else
end

% Wait
WaitSecs(1*TR);
clear ans


%% Start trials

% trial = 1;
% for trial = 1:4
for trial = 1:size(timings,2)

    %% Set up trial
    
    % Get key details for this trial
    currfing = timings(row_fing,trial);
    currfreq = timings(row_freq,trial);
    currtime_cum = timings(row_realtime_cum,trial);
    
    % Stimulation trial or deadTRs?
    if currfing == 0
        
        % % DeadTRs
        % Wait for trigger - where relevant
        if trial == 1
        
            % Set timeout boolean
            if run_num == 0
                % does not wait for trigger
                timedout_tr = true;
            else
                % DOES wait for trigger
                timedout_tr = false;
            end

            % Wait for trigger
            while ~timedout_tr
                if psychvis == 1  
                    % say we are waiting
                    DrawFormattedText(window, sprintf('Waiting for scanner'), 'center', 'center', [0 0 0]);
                    Screen('Flip', window);
                else
                end

                % Check for scanner trigger
                [ ~, ~, keyCode ] = KbCheck;

                % if(keyIsDown), break; end
                if( strcmp(KbName(keyCode), '5%') ), timedout_tr = true; end
            end

            % Start both timers
            if timedout_tr == true
                t0 = GetSecs; tic
            end
            clear keyCode timedout_tr

            % Redraw black fixation
            if psychvis == 1
                Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 0], [xCentre yCentre], 2);
                Screen('Flip', window);
            else
            end
            
        % end of if trial == 1  
        else  
        end
        
    else
        
        % % Stimulation trial
        % Get name of stimulation and finger so can pull out of stims for this trial
        tacname = sprintf('tac_f%d', currfreq);
        fingname = sprintf('t%d', currfing);

        % Pull correct sound out of stims for this trial
        playstim = stims.(tacname).(fingname);
        clear tacname fingname
        
            % FOR DEBUGGING ONLY - Tells you what freq and finger
            if tactorsOn == 0
                DrawFormattedText(window, sprintf('[debugging info as tactors off]\n\n fing %d\nfreq %d', currfing, currfreq), 'center', 'center', [0 0 0]); Screen('Flip', window);
            else
            end
            
        % Load then play sound
        if tactorsOn == 1
            PsychPortAudio('FillBuffer', pahandle, playstim);
            PsychPortAudio('Start', pahandle, 1, 0);
        else
        end
        clear playstim
        
    % end of stim trial vs. dead TRs (currfing ==0)
    end
    
    % Wait until set time
    WaitSecs('UntilTime', t0 + currtime_cum );
    clear currtime_cum currfing currfreq ans
    
        % FOR DEBUGGING ONLY - Presents blue fixation to say stimulation is over
        if tactorsOn == 0
            Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 1], [xCentre yCentre], 2); Screen('Flip', window);
        else
        end
        
    % Add to timings - Stimulation
    timings(row_tictoctime,trial) = toc; tic
    timings(row_tictoctime_cum,trial) = sum(timings(row_tictoctime,:));


% End trial loop
end

% Get run timing
time.intended = round(sum(timings(row_realtime,:))/60,4);
time.actual = round(sum(timings(row_tictoctime,:))/60,4);

clear t0
toc;
clear ans

% Re-enable echo to the command line for key presses (CTRL+C to exit)
ListenChar(1);
RestrictKeysForKbCheck([]);

% Close audio
PsychPortAudio('Close');
clear pahandle

% Close psychtool visuals
sca
clear allCoords lineWidthPix screenNumber window windowRect xCentre yCentre
clear ans

% Save blocks data
save([datadir, filename]);


%% Get predicted time versus actual times

% Turn off short form
format short g

% Get difference between predicted and actual
timings(size(timings,1)+1,:) = timings(row_tictoctime,:) - timings(row_realtime,:); % row 1 comes from tic/toc (actual), row 3 is pre generated, actual durs based on TRs
timings(size(timings,1)+1,:) = timings(row_tictoctime_cum,:) - timings(row_realtime_cum,:); % as above, but cumulative (summed over all timings so far)

% Round to 4 DP
timings(size(timings,1)-1,:) = round(timings(size(timings,1)-1,:),4);
timings(size(timings,1),:) = round(timings(size(timings,1),:),4);

% Save data - not sure why these aren't the same
timings_predMinusActual.individTrials = sum(timings(size(timings,1)-1,:));
timings_predMinusActual.cumulative = sum(timings(size(timings,1),:));

% plot(timings(1,:)); hold on; plot(timings(row_t_realTRtime,:)); hold off
% plot(timings(2,:)); hold on; plot(timings(4,:)); hold off


%% Get stimulus timing files

fall = [datadir, filename '_timings.txt'];
fidall = fopen(fall, 'wt');

f1 = [datadir, filename, sprintf('_timings%dHz.txt', freqs(1)) ];
fid1 = fopen(f1, 'wt');

f2 = [datadir, filename, sprintf('_timings%dHz.txt', freqs(2)) ];
fid2 = fopen(f2, 'wt');

f3 = [datadir, filename, sprintf('_timings%dHz.txt', freqs(3)) ];
fid3 = fopen(f3, 'wt');

for s = 1:size(timings,2)
    
    % All times
    if timings(row_freqChange,s) == 1
        % Is the first freq for that finger, i.e., stimualtion starting for that finger
        fprintf(fidall, [num2str(timings(row_realtime_cum,s)) ' '] );
    else
    end
        
    % Specific freqs
    if timings(row_freq,s) == freqs(1)
        fprintf(fid1, [num2str(timings(row_realtime_cum,s)) ' '] );
        
    elseif timings(row_freq,s) == freqs(2)
        fprintf(fid2, [num2str(timings(row_realtime_cum,s)) ' '] );
          
    elseif timings(row_freq,s) == freqs(3)
        fprintf(fid3, [num2str(timings(row_realtime_cum,s)) ' '] );
        
    else
    end
    
end
clear s

fclose(fidall); fclose(fid1); fclose(fid2); fclose(fid3);
clear fall f1 f2 f3 fidall fid1 fid2 fid3

clear row_fing row_freq row_freqChange row_realtime row_realtime_cum row_realTRtime row_realTRtime_cum row_tictoctime row_tictoctime_cum
clear ans


%% Final save

save([datadir, filename]);

