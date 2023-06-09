
% % TO DO
% Change things for PC - homedir (116)
% CHECK WHAT NUMBERS COME OUT OF BUTTON BOX AND ADJUST ISCOR CALC FOR THIS
% work out what amp is good??

% % TO DO LATER
% EDIT TR IF NEEDED

% % To check
% Block and trial are right number (313, 337)

% % AY as of 12/4
% keycodes are set up so that digit 2 can be responded to with button 1,
% etc. The correct/incorrect calculation has been amended to address this.
% The above has been tested re: accuracy and miss information calculated at
% the end of the block, appropriate numbers shown (ignoring thumb).
% command window outputs the frequency stimulated when stimulating, as well
% as the target finger. Also outputs that stims are not playing during
% rest/dead TR time.
% still need to add hte total number of measurements for sequence setup.


%% Clean up

% Matlab cleaning things
sca;
close all;
clearvars;


%% Important tactor and sound card settings

% Remind to set comp vol and amp vol
input(sprintf('Set comp vol to X, turn knobs on amp to full'));

% Remind to check tactor orders
input(sprintf('Check tactor orders before starting'));
clear ans

% Set which computer: 0 = home mac, 1 = scanner PC
scannerPC = 1;

% Set number of channels - WONT EVER CHANGE FROM 6
num_chans = 6;

% Set number of tactors on
num_tactors = 5;

% Pre-set order for tactors (need to put in a weird order for them to play 1-5?)
tacorder_yn = 0; % pre-set order needed

% Pulse type is regular (1) or spaced pulse (2) version (spaced pulse is a short single pulse (pos values only) delivered at different ISIs to get the frequency - this is to deal with issue of the lower frequencies not feeling very intense)
pulsetype = 2;

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

% Record from thumb for manipulation check? 1 = yes, 0 = no
record_thumb = 0;

% turn off sci notation
format long g


%% Scanning details

% Number of TRs before stimulation starts
deadTRs = 5; % should be 5 (at start AND end of block)

% TR
TR = 1.920; % Ash's old TR was 1.992 (NOT USING)

% [old not using - setting difdur as a function of freq now in make_sound] Set duration of longer/shorter stimulation (oddball)
difdur = 1/3; % .333 sec, enough to lose 1 pulse in 3Hz cond


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
filename = ['scan_data_', subcode, '_', p_init, '_run', num2str(run_num), '_', datetag];

% Pop filename on screen so experimenter can check participant dets and cancel out if details are wrong
input(sprintf('Check participant dets: %s - exit if incorrect', filename));
clear ans


%% Make dir for that participant in Data dir if it doesn't exist already

% Set home directory
if scannerPC == 0
    homedir = 'C:\Users\meduser\Documents\FingertipMappingMND\Columns\';%'/Users/uqhdemp1/Documents/2022/Columns II/Scanner task'; % office mac
else
    homedir = 'C:\Users\meduser\Documents\FingertipMappingMND\Columns\'; %'ADD'; % ADD FOR STIMS PC
end

% Set data directory
if scannerPC == 0
    % Set to individual sub folder
    datadir = [homedir, '/Data/', subcode, '_', p_init,'/'];
    
    % Make individual sub name folder if it's not there already
    if ~exist(datadir, 'dir')
    mkdir(datadir);
    end

else
    % Set to data general folder - as cannot make new directories in matlab on scanner PC
    datadir = [homedir, '\Data\'];
end
clear homedir


%% Make sounds

% Common sound settings for all sounds
amp = 7; % May need to work out what is ideal
Fs = 48000; % need to use this for PC
phase = 0; % phase shift - we aren't using this so set to 0

% Sound settings that vary
durs = [3*TR 4*TR 5*TR]; % in seconds
freqs = [3 30]; % in Hz

% Make sound
make_sound_310822


%% Set up experiment

% Number of trials & blocks
if run_num == 0
    % training
    trials = 4;
    blocks = 1;
else
    % main exp
    trials = 30; % should be 30 -  otherwise 20min blocks
    blocks = 2; % should be 2
end

% Load scanner timing & freq details
load('stimTRlist_1persub_250721.mat'); % TRs = 3, 4 or 5
load('freqlist_1persub_250721.mat'); % start with 3 or 30 first in block 1/2

% Cut down to those needed
stimTRs = stimTRlist(:, :, subnum);
subfreqs = freqlist(:,:,subnum);
clear stimTRlist subnum
clear freqlist


%% Create timing matrix

% Initialise timing matrix - the extra 2 are for the dead TRs (start & finish)
row_t_realTRtime = 3;
timings = zeros(7, (trials*2*blocks) + 2*blocks);

% Start counter
c = 0;

% Loop to add in desired times
for b = 1:blocks
    
    % Start second counter for trials
    ct = 0;
    
    for t = 1:trials*2+2
        c = c + 1;
        
        if t == 1
            % Put dead TRs
            timings(row_t_realTRtime,c) = deadTRs * TR;
        elseif ~mod(t,2) && t ~= trials*2+2
            % Put stimulus times in at all even positions (except 1)
            ct = ct+1;
            timings(row_t_realTRtime,c) = stimTRs(b, ct) * TR;
        elseif mod(t,2) && t ~=1
            % Put break times in all odd positions (except 1)
            timings(row_t_realTRtime,c) = 1 * TR;
        elseif t == trials*2+2
            % Put dead TRs
            timings(row_t_realTRtime,c) = deadTRs * TR;
        end
        
        % Add cumulatively
        timings(4,c) = sum(timings(row_t_realTRtime,:));
    end
end

clear b t c ct


%% Initialise Psychtoolbox things

% % Audio
% Make sure any old audio stuff is closed
PsychPortAudio('Close');

% Initialises sound driver...the 1 pushes for low latency
InitializePsychSound(1);

% Initialise two sound buffers for the two sounds
pahandle = PsychPortAudio('Open', [], [], 2, Fs, num_chans, 0); % for the first played sound

% % play test sound - load into buffer then play then wait
PsychPortAudio('FillBuffer', pahandle, testall); PsychPortAudio('Start', pahandle, 1, 0); WaitSecs(1);
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
    [window, windowRect] = PsychImaging('OpenWindow', screenNumber, 255/2);
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


%% Start Block loop

% Intialise new timing counter for getting experimental times
tm = 0;

% block = 1;
% for block = 1:1
for block = 1:blocks
        
    % Make blockname
    blockname = sprintf('block%d', block);
    
    % Get freqs for this block
    freqs = subfreqs(block, :);
    
    % Create output matrix for this block
    row_freq = 1; row_oddball = 2; row_resp = 3; row_iscor = 4; row_tictoctime = 5; row_tictocITI = 6; row_TRtime = 7; row_TRITI = 8; row_TRs = 9;
    output = zeros(9, trials); % freq, oddfing, resp, iscor, stim time, gap time, stim time diff, gap time diff, stimTRs
    
    % Create oddball finger list
    oddfinglist = Shuffle(repmat(1:num_tactors, 1, round(trials/num_tactors)));
    oddfinglist = oddfinglist(1, 1:trials); % shorten if needed
    
    % Get number of TRs
    TRs.(blockname) = sum(timings(row_t_realTRtime,:)/TR);
        
    
    %% Start trial
    
    % trial = 1;
    % for trial = 1:4
    for trial = 1:trials

        %% Set up trial

        % Get freq for this trial
        if mod(trial,2)
            freq = freqs(1);
        else
            freq = freqs(2);
        end
        
        % Get dur for this trial
        dur = stimTRs(block,trial) * TR;
        dur_char = num2str(dur);
        dur_char1 = extractBefore(dur_char, '.');
        dur_char2 = extractAfter(dur_char, '.');
        clear dur dur_char
        
        % Get odd finger for this trial
        oddfing = oddfinglist(trial);
        
        % Get right sound for this trial given above freq, dur info
        trialname = sprintf('tac_f%d_d%sp%s', freq, dur_char1, dur_char2);
        trialstim = stims.(trialname);
        clear dur_char1 dur_char2 trialname
        
        % Select sound with oddball you want for that trial
        playname = sprintf('t%d', oddfing);
        playstim = trialstim.(playname);
        clear playname trialstim

        % Add details of this trial into output
        output(row_freq, trial) = freq; % freq
        output(row_TRs, trial) = stimTRs(block,trial); % TRs
        output(row_oddball,trial) = oddfing; % oddball

        % Set resp to 999 (so we can see if missed) - otherwise will stay as 0
        resp = 999;
        iscor = 999;
        
        
        %% Run stimulation

        if psychvis == 1
            % Redraw black fixation (to remove red/green if there on prev trial)
            Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 0], [xCentre yCentre], 2);
            Screen('Flip', window);
        else
        end

        
        if trial == 1
            % Add to timings counter (1st dead TRs)
            tm = tm+1;
            
            if block == 1
                
                % Set timeout boolean
                if run_num == 0
                    % does not wait for trigger
                    timedout_tr = true;
                else
                    % DOES wait for trigger
                    timedout_tr = false;
                end
                                              
                while ~timedout_tr
                    if psychvis == 1  
                        % say we are waiting
                        DrawFormattedText(window, sprintf('Waiting for trigger'), 'center', 'center', [0 0 0]);
                        Screen('Flip', window);
                    else
                    end
                    
                    % Check for scanner trigger
                    [ ~, ~, keyCode ] = KbCheck;

                    % if(keyIsDown), break; end
                    if( strcmp(KbName(keyCode), '5%') ), timedout_tr = true; end
                end
                
                if timedout_tr == true
                    % Restrict for all keys except 1-5 (trigger should be suppressed as is 5% inside psychtoolbox) - CHECK THIS WORKS
%                     nums = '12345'; % AY this only works for numpad, not scanner buttons
%                     keynames = mat2cell(nums, 1, ones(length(nums), 1));
                    keynames = {};
                    keynames{1, 1} = '1!'; keynames{1, 2} = '2@'; keynames{1, 3} = '3#';keynames{1, 4} = '4$';keynames{1, 5} = '5%';
                    keynames = KbName(keynames);
                    RestrictKeysForKbCheck(keynames);
                    clear keynames nums ans
                    
                    
                    % Start both timers
                    t0 = GetSecs; tic
                end
                
                clear keyCode timedout_tr
                
                if psychvis == 1
                    % Redraw black fixation
                    Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 0], [xCentre yCentre], 2);
                    Screen('Flip', window);
                else
                end
            
            else
            end

                % Wait (first dead TRs)
                WaitSecs('UntilTime', t0 + timings(4,tm) );
                clear ans

                % Add to timings - first dead TRs
                timings(1,tm) = toc; tic
                timings(2,tm) = sum(timings(1,:));
        
        % end trial = 1 loop    
        else
        end
                
        % % % Stimulation
        % Add to timings counter - Stimulation
        tm = tm+1;
        
                % FOR DEBUGGING ONLY - Tells you what freq and oddball
%                 DrawFormattedText(window, sprintf('freq %d, oddball %d', freq, oddfing), 'center', 'center', [0 0 0]); Screen('Flip', window);
        % Tell operator which freq is playing, and which is the target
        % finger
        sprintf('freq %d, oddball %d', freq, oddfing)
        
        % Play sound - load then play
        PsychPortAudio('FillBuffer', pahandle, playstim); PsychPortAudio('Start', pahandle, 1, 0);
        WaitSecs('UntilTime', t0 + timings(4,tm) );
        clear ans playstim

        % Add to timings - Stimulation
        timings(1,tm) = toc; tic
        timings(2,tm) = sum(timings(1,:));
        
        % Add to output/ timings mats - Stimulation (extra)
        output(row_tictoctime,trial) = timings(1,tm); % actual time (tic toc)
        output(row_TRtime,trial) = timings(row_t_realTRtime,tm); % expected time (TR * seconds)
        timings(5,tm) = freq;
        
        clear freq

                % FOR DEBUGGING ONLY - Presents blue fixation to say stimulation is over
                % Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 1], [xCentre yCentre], 2); Screen('Flip', window);


        %% Post stimulation period
        
        % Add to timer counter - ITI
        tm = tm+1;
        
        % % % Check for resp
        if psychvis == 1
            
            % Timeout boolean
            timedout_iti = false;

            while ~timedout_iti
                % Check if a key is pressed
                [ keyIsDown, keyTime, keyCode ] = KbCheck;
                if(keyIsDown), break; end
                if( (keyTime - t0) > timings(4,tm) ), timedout_iti = true; end
            end

            % Store key pressed
            if(~timedout_iti)
                respd = KbName(keyCode);
                resp = str2double(respd(1));
                % resp = str2double(KbName(keyCode));
            end
            
        else
        end

        clear respd
        clear timedout_iti keyIsDown keyTime keyCode
        clear ans
        
        
        %% Calc accuracy and display

        % Add details into matrix
        output(row_resp, trial) = resp;

        % Check correct (if not a miss '999')
        if resp ~= 999
            if oddfing == resp+1 %AY this accounts for the 4 buttons box responding to D2:D5
                % Correct
                iscor = 1;
            else
                % Incorrect
                iscor = 0;
            end
        else
        end
        clear resp oddfing
        
        % Add corr dets
        output(row_iscor, trial) = iscor;
        
        % HAVE REMOVED TRIAL BY TRIAL FEEDBACK FOR NOW, AS WE DON'T HAVE A 5 FINGER BUTTON BOX SO CAN'T GIVE FEEDBACK ON PERFORMANCE FOR THUMB
%         % Change fixation colour depending on iscor (note - putting in a colour fixation for missed does not work as it needs to break early to see fix, which it only can do if there is a response)
%         if psychvis == 1
%             if iscor == 1
%                 % For correct
%                 Screen('DrawLines', window, allCoords, lineWidthPix, [0 1 0], [xCentre yCentre], 2);
%             elseif iscor == 0
%                 % For incorrect
%                 Screen('DrawLines', window, allCoords, lineWidthPix, [1 0 0], [xCentre yCentre], 2);
%             else
%             end
% 
%             % Draw chosen fixation
%             Screen('Flip', window);
%         else
%         end

        clear iscor
        
        % Wait (back up post oddball wait, in case of key-press breaking early)
        WaitSecs('UntilTime', t0 + timings(4,tm) );
        clear ans
 
        % Add to timings - ITI
        timings(1,tm) = toc; tic
        timings(2,tm) = sum(timings(1,:));
        
        % Add to timings - ITI (extra)
        output(row_tictocITI,trial) = timings(1,tm);
        output(row_TRITI,trial) = timings(row_t_realTRtime,tm);
               
        % End trial loop
    end
        
    % tell experimenter that nothing is playing on stims
    sprintf('stims not playing')
    
    %% end Dead TRs
    
    if psychvis == 1
        % Redraw black fixation (to remove red/green if there on prev trial)
        Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 0], [xCentre yCentre], 2);
        Screen('Flip', window);
    else
    end
    
    % Add to timer counter - end dead TRs
    tm = tm+1;
    
    WaitSecs('UntilTime', t0 + timings(4,tm) );
    clear ans
    
    % ADDED_H23 tell exp dead TRs over
    sprintf('Dead TRs over')

    % Add to timings - end dead TRs
    timings(1,tm) = toc; tic
    timings(2,tm) = sum(timings(1,:));

   
    %% End of block stuff
    
    clear oddfinglist trial block
        
    % Save blocks data
    ALLoutput.(blockname) = output;
    save([datadir, filename]);
    clear output blockname
    
    
% End block loop
end

% Get run timing
time.intended = round(sum(timings(row_t_realTRtime,:))/60,4);
time.actual = round(sum(timings(1,:))/60,4);

clear t0 tm
toc;
clear ans

% Re-enable echo to the command line for key presses (CTRL+C to exit)
ListenChar(1);
RestrictKeysForKbCheck([]);

% Close audio
PsychPortAudio('Close');

clear pahandle


%% Get total number of each stimulus type presented

% Get all data in one matrix
alloutput = [];
for b = 1:blocks
    blockname = sprintf('block%d',b);
    alloutput = horzcat(alloutput, ALLoutput.(blockname));
end
clear b blockname

% Get how many 3 and 30 trials presented
total3 = 0; total30 = 0;
for t = 1:size(alloutput,2)
    if alloutput(1,t) == 3
        total3 = total3+1;
    elseif alloutput(1,t) == 30
        total30 = total30+1;
    else
    end
end
clear t alloutput


%% Calc % corr

% Separate missed and responded trials - remove thumb trials if we were not recording from thumb
missed = [];
responded = [];
m = 0;
r = 0;

for b = 1:blocks
    % get data for each block
    blockname = sprintf('block%d',b);
    data_block = ALLoutput.(blockname);
    
    % If not recording from thumb, remove thumb trials from data before moving forward
    if record_thumb == 0
        data_block( :, data_block(row_oddball,:)==1 ) = [];
    end
    
    for tl = 1:size(data_block,2)
        % Was missed or responded
        if data_block(row_resp,tl) == 999
            m = m+1;
            missed(:,m) = data_block(:,tl);
        else
            r = r+1;
            responded(:,r) = data_block(:,tl);
        end
    end
%     clear blockname data_block
end
clear m r tl b data

% Calc perc missed & corr (from responded)
if isempty(missed)
    percmiss = 0;
else
    percmiss = ( size(missed,2) / (size(missed,2)+size(responded,2)) )*100;
end

if isempty(responded)
    perccorr = 0;
else
    perccorr = ( sum(responded(4,:)) / (size(missed,2)+size(responded,2)) )*100;
end

% Store
ALLmissed = missed;
ALLresponded = responded;
SCORES.percmiss = percmiss;
SCORES.perccorr = perccorr;

% Round for display
percmiss = round(percmiss);
perccorr = round(perccorr);

if psychvis == 1
    % Present info
    DrawFormattedText(window, sprintf('Yay! Run %d is over.\n\n You got %d%% correct.\n\n You missed %d%%.\n\n Please keep lying still :)', run_num, perccorr, percmiss), 'center', 'center', [0 0 0]);
    Screen('Flip', window);
else
end

% Wait so they can read
WaitSecs(1*TR);

clear perccorr percmiss
clear allCoords lineWidthPix screenNumber window windowRect xCentre yCentre


%% Calc % corr separately for freq 1 and freq 2 - responded trials
for measure = 1:2
    
    if measure == 1
        subdata = missed;
    else
        subdata = responded;
    end
    
    f3 = 0;
    f30 = 0;
    data3 = [];
    data30 = [];

    for c = 1:size(subdata,2)
        if subdata(row_freq,c) == 3
            f3 = f3+1;
            data3(1,f3) = subdata(row_iscor,c);
        elseif subdata(row_freq,c) == 30
            f30 = f30+1;
            data30(1,f30) = subdata(row_iscor,c);
        else
        end
    end
    clear c subdata
    
    if measure == 1
        % Missed
        SCORES.nummissed3 = f3;
        SCORES.nummissed30 = f30;
        % SCORES.percmissed3 = ( f3 / total3 )*100; % think this not so informative - changed 310822
        % SCORES.percmissed30 = ( f30 / total30 )*100; ''
    else
        % Responded 3
        if isempty(data3)
            SCORES.perccorr3 = 0;
        else
            SCORES.perccorr3 = ( sum(data3) / size(data3,2) )*100;
            % SCORES.perccorr3 = ( sum(data3) / total3 )*100; % think this not so informative - changed 310822
        end
        
        % Responded 30
        if isempty(data30)
            SCORES.perccorr30 = 0;
        else
            SCORES.perccorr30 = ( sum(data30) / size(data30,2) )*100;
            % SCORES.perccorr30 = ( sum(data30) / total30 )*100; think this not so informative - changed 310822
        end
    end
    
    clear f3 f30 data3 data30
    
end

clear missed responded measure ans
clear row_freq row_iscor row_oddball row_resp row_tictocITI row_tictoctime row_TRITI row_TRs row_TRtime


%% Final timing things

% Turn off short form
format short g

% Get difference between predicted and actual
timings(6,:) = timings(1,:) - timings(row_t_realTRtime,:); % row 1 comes from tic/toc (actual), row 3 is pre generated, actual durs based on TRs
timings(7,:) = timings(2,:) - timings(4,:); % as above, but cumulative (summed over all timings so far)

% Round to 4 DP
timings(6,:) = round(timings(6,:),4);
timings(7,:) = round(timings(7,:),4);

% Save data - not sure why these aren't the same
timings_predMinusActual.individTrials = sum(timings(6,:));
timings_predMinusActual.cumulative = sum(timings(7,:));

% plot(timings(1,:)); hold on; plot(timings(row_t_realTRtime,:)); hold off
% plot(timings(2,:)); hold on; plot(timings(4,:)); hold off

% Get stimulus timing files
s3 = [datadir, filename '_timings3Hz.txt'];
fid3 = fopen(s3, 'wt');

s30 = [datadir, filename '_timings30Hz.txt'];
fid30 = fopen(s30, 'wt');

for s = 1:size(timings,2)
    if timings(5,s) == 3
        fprintf(fid3, [num2str(timings(row_t_realTRtime,s)) ' '] );
    elseif timings(5,s) == 30
        fprintf(fid30, [num2str(timings(row_t_realTRtime,s)) ' '] );
    else
    end
end

fclose(fid3); fclose(fid30);
clear s s3 fid3 s30 fid30
clear row_t_realTRtime


%% Final save

% ADDED_H23 tell exp closing
sprintf('End calcs - closing')
    
save([datadir, filename]);

sca

clear psychtool ans
