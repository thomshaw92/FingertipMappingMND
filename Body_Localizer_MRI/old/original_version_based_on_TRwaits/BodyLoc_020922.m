

% % TO DO
% Change things for PC - homedir (116)
% Add input varibles for participant details - now puts in auto
% Add listenchar(2) blocker back in - commented now
% Put visuals back on

% % TO DECIDE
% Dead TRs at start and end
% How long rests (guess is same as stimulation blocks? 12s does not say in paper)

% % TO DO LATER
% EDIT TR IF NEEDED


%% Clean up

% Matlab cleaning things
sca;
close all;
clearvars;

% turn off sci notation
format long g


%% Scanning details

% Number of TRs before stimulation starts
deadTRs = 5; % How many do we want??

% Movement TRs
moveTRs = 7; % How many do we want??

% Rest TRs
restTRs = moveTRs;

% TR
TR = 1.920; % EDIT


%% Get subj & filename details

% Input participant details
p_init = 'AY'; subnum = 1; run_num = 1; % JUST FOR PILOTING
% p_init = input('Participant Intitials: ', 's');
% subnum = input('SUBJECT Number: ');
% run_num = input('Run Number (0 for training): ');

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
filename = ['BodyLoc_', subcode, '_', p_init, '_run', num2str(run_num), '_', datetag];

% Pop filename on screen so experimenter can check participant dets and cancel out if details are wrong
input(sprintf('Check participant dets: %s - exit if incorrect', filename));
clear ans


%% Make dir for that participant in Data dir if it doesn't exist already

% Set home directory
homedir = '/Users/uqhdemp1/Documents/2022/MND/Body Loc'; % office mac
% homedir = ADD FOR STIMS PC;

% Set data directory
datadir = [homedir, '/Data/', subcode, '_', p_init,'/'];
% PC % datadir = [homedir, '\Data\', subcode, '_', p_init,'\'];
clear homedir

if ~exist(datadir, 'dir')
    mkdir(datadir);
end


%% Set up experiment

% Number of trials & blocks
if run_num == 0
    % training
    blocks = 1;
else
    % main exp
    blocks = 4; % should be 4
end

% Load condition order
load('BodyLoc_all_order.mat');

% Cut down to those needed for this sub - 4 blocks per person (e.g., if sub 1 - take first 4 rows)
subconds = all_orders_rand((subnum-1)*4+1:(subnum-1)*4+4,:);
clear all_orders_rand


%% Set up data saving matrices

% Timings mat - row 1 (actual secs), row 2 (event type), row 3 (predicted secs)
timings = zeros(3,1);

% events = [];


%% Initialise Psychtoolbox things

% % Keyboard
% Make so works across different keyboards
KbName('UnifyKeyNames');

% Restrict for all keys except %5 (trigger) when doing kbchecks in psychtoolbox
keynames = KbName({'5%'});
RestrictKeysForKbCheck(keynames);
clear keynames ans

% Suppress output from keyboard - to stop trigger popping into command window - ADD IN LATER
% ListenChar(2);

% [leave commented out ALWAYS] Reallow keyboard 
% ListenChar(1); RestrictKeysForKbCheck([]);


% % % Visuals
% % Initialise some set up parameters
% PsychDefaultSetup(2);
% 
% %Choosing the display
% screens=Screen('Screens'); screenNumber=max(screens); clear screens
% 
% %Open Screen
% % [window, windowRect] = PsychImaging('OpenWindow', screenNumber, 255/2);
% [window, windowRect]=Screen('OpenWindow', screenNumber,[], [10 20 600 300]); % small debugging window
% 
% % Set screen parameters
% Screen('TextSize', window, 40);
% 
% % Set up alpha-blending for smooth (anti-aliased) lines --> fixation cross below wont run without it
% Screen('BlendFunction', window, 'GL_SRC_ALPHA', 'GL_ONE_MINUS_SRC_ALPHA');
% 
% % Set things up for fixation cross
% [xCentre, yCentre] = RectCenter(windowRect); fixCrossDimPix = 40; xCoords = [-fixCrossDimPix fixCrossDimPix 0 0]; yCoords = [0 0 -fixCrossDimPix fixCrossDimPix]; allCoords = [xCoords; yCoords]; clear fixCrossDimPix xCoords yCoords; lineWidthPix = 4;
% 
% clear ans


%% Present general instructions on screen

% % Instruction
% DrawFormattedText(window, sprintf('Please move the body part instructed on screen \n for the whole time the message is on screen\n\n Please also try to keep your head as still as possible \n\n Thank you!'), 'center', 'center', [0 0 0]);
% Screen('Flip', window);

% Wait
WaitSecs(1*TR);
clear ans


%% Set up some generic instruction messages

% Get rest message
msg_rest = sprintf('Please rest (lie still)');

% Get get ready to move message
msg_get_ready = sprintf('Get ready to move \n\n (but stay still for now)');
        
        
%% Wait for first trigger then pause for dead TRs

% % Say we are waiting
% DrawFormattedText(window, sprintf('Waiting for scanner'), 'center', 'center', [0 0 0]);
% Screen('Flip', window);

% Start TR counter
ctr = 0;

% Start event counter
% ev = 0;

% Set how many triggers to wait for
wait_for = deadTRs;

% Set event type
event_type = 555; % Dead TRs

% Run wait
wait_for_trigger


%% Start Block loop

block = 1;
% for block = 1:1
% for block = 1:blocks
        
    % Make blockname
    blockname = sprintf('block%d', block);
    
    % Get conds for this block
    subcond_block = subconds(block, :);
    

    %% Start trial - to loop through body parts
    
    trial = 1;
    % for trial = 1:2
    % for trial = 1:trials

        %% Set up trial

        % Get cond for this trial
        cond_name_trial = cond_names(trial);
        
        % Generate move message
        msg_move = sprintf('Please move your %s', cond_name_trial)
        
        % Present move message on screen
        % DrawFormattedText(window, msg_rest, 'center', 'center', [0 0 0]);
        % Screen('Flip', window);
        
        % Set how many triggers to wait for
        wait_for = moveTRs;

        % Set event type
        event_type = trial; % Movement trial number

        % Run wait
        wait_for_trigger
        
        
        
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
        output(1, trial) = freq; % freq
        output(9, trial) = stimTRs(block,trial); % TRs
        output(2,trial) = oddfing; % oddball

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
                    nums = '12345';
                    keynames = mat2cell(nums, 1, ones(length(nums), 1));
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
                % DrawFormattedText(window, sprintf('freq %d, oddball %d', freq, oddfing), 'center', 'center', [0 0 0]); Screen('Flip', window);
                    
        % Play sound - load then play
        PsychPortAudio('FillBuffer', pahandle, playstim); PsychPortAudio('Start', pahandle, 1, 0);
        WaitSecs('UntilTime', t0 + timings(4,tm) );
        clear ans playstim

        % Add to timings - Stimulation
        timings(1,tm) = toc; tic
        timings(2,tm) = sum(timings(1,:));
        
        % Add to output/ timings mats - Stimulation (extra)
        output(5,trial) = timings(1,tm); % actual time
        output(7,trial) = timings(3,tm); % expected time
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
        output(3, trial) = resp;

        % Check correct (if not a miss '999')
        if record_thumb == 0 && oddfing == 1
            % If we are NOT recording from thumb, and its a thumb trial, i.e., no data coming in
            if resp ~= 999
                % Say it is right no matter what the resp is (if there is one, if missed, leave as missed)
                iscor = 1;
            else
            end
        else
            % Actually check performance
            if resp ~= 999
                if oddfing == resp
                    % Correct
                    iscor = 1;
                else
                    % Incorrect
                    iscor = 0;
                end
            else
            end
        end

        clear resp oddfing
        
        % Add corr dets
        output(4, trial) = iscor;
        
        if psychvis == 1
        % Change fixation colour depending on iscor (note - putting in a colour fixation for missed does not work as it needs to break early to see fix, which it only can do if there is a response)
        if iscor == 1
            % For correct
            Screen('DrawLines', window, allCoords, lineWidthPix, [0 1 0], [xCentre yCentre], 2);
        elseif iscor == 0
            % For incorrect
            Screen('DrawLines', window, allCoords, lineWidthPix, [1 0 0], [xCentre yCentre], 2);
        else
        end

        % Draw chosen fixation
        Screen('Flip', window);
        else
        end

        clear iscor

        % Wait (back up post oddball wait, in case of key-press breaking early)
        WaitSecs('UntilTime', t0 + timings(4,tm) );
        clear ans
 
        % Add to timings - ITI
        timings(1,tm) = toc; tic
        timings(2,tm) = sum(timings(1,:));
        
        % Add to timings - ITI (extra)
        output(6,trial) = timings(1,tm);
        output(8,trial) = timings(3,tm);
 
    % End trial loop
    end
    
    
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
time.intended = round(sum(timings(3,:))/60,4);
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

% Separate missed and responded trials
missed = [];
responded = [];
m = 0;
r = 0;

for b = 1:blocks
    % get data for each block
    blockname = sprintf('block%d',b);
    data = ALLoutput.(blockname);
    
    for tl = 1:trials
        % Was missed or responded
        if data(3,tl) == 999
            m = m+1;
            missed(:,m) = data(:,tl);
        else
            r = r+1;
            responded(:,r) = data(:,tl);
        end
    end
    clear blockname
end
clear m r tl b data

% Calc perc missed & corr (from responded)
if isempty(missed)
    percmiss = 0;
else
    percmiss = ( size(missed,2) / (trials*blocks) )*100;
end

if isempty(responded)
    perccorr = 0;
else
    perccorr = ( sum(responded(4,:)) / size(responded,2) )*100;
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

clear perccorr percmiss run_num
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
        if subdata(1,c) == 3
            f3 = f3+1;
            data3(1,f3) = subdata(4,c);
        elseif subdata(1,c) == 30
            f30 = f30+1;
            data30(1,f30) = subdata(4,c);
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
clear freqs blocks


%% Final timing things

% Turn off short form
format short g

% Get difference between predicted and actual
timings(6,:) = timings(1,:) - timings(3,:); % row 1 comes from tic/toc (actual), row 3 is pre generated, actual durs based on TRs
timings(7,:) = timings(2,:) - timings(4,:); % as above, but cumulative (summed over all timings so far)

% Round to 4 DP
timings(6,:) = round(timings(6,:),4);
timings(7,:) = round(timings(7,:),4);

% Save data - not sure why these aren't the same
timings_predMinusActual.individTrials = sum(timings(6,:));
timings_predMinusActual.cumulative = sum(timings(7,:));

% plot(timings(1,:)); hold on; plot(timings(3,:)); hold off
% plot(timings(2,:)); hold on; plot(timings(4,:)); hold off

% Get stimulus timing files
s3 = [datadir, filename '_timings3Hz.txt'];
fid3 = fopen(s3, 'wt');

s30 = [datadir, filename '_timings30Hz.txt'];
fid30 = fopen(s30, 'wt');

for s = 1:size(timings,2)
    if timings(5,s) == 3
        fprintf(fid3, [num2str(timings(2,s)) ' '] );
    elseif timings(5,s) == 30
        fprintf(fid30, [num2str(timings(2,s)) ' '] );
    else
    end
end

fclose(fid3); fclose(fid30);
clear s s3 fid3 s30 fid30


%% Final save

save([datadir, filename]);

sca

clear psychtool ans
