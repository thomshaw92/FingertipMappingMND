

% % TO DO
% Change things for PC - homedir (116)
% Add input varibles for participant details - now puts in auto
% Add listenchar(2) blocker back in - commented now

% % TO DECIDE
% Dead TRs at start and end
% Dead TRs between blocks?
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
TRsdead = 8; % edited 12/4
% TRsdead = 5; % How many do we want??

% Movement TRs
TRsmove = 11; % edited 12/4
% TRsmove = 7; % edited from 6 to 7

% Rest TRs
TRsrest = TRsmove;

% TR
TR = 1.00; % edited 12/04/23
% TR = 1.466; % edited 9/1/23


%% Get subj & filename details

% Input participant details
% p_init = 'AY'; subnum = 1; run_num = 1; % JUST FOR PILOTING
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
filename = ['BodyLoc_', subcode, '_', p_init, '_run', num2str(run_num), '_', datetag];

% Pop filename on screen so experimenter can check participant dets and cancel out if details are wrong
input(sprintf('Check participant dets: %s - exit if incorrect', filename));
clear ans


%% Make dir for that participant in Data dir if it doesn't exist already

% Set home directory
homedir = 'C:\Users\meduser\Documents\FingertipMappingMND\Body_Localizer_MRI';%uqhdemp1/Documents/2022/MND/Body Loc'; % office mac
% homedir = ADD FOR STIMS PC;

% Set data directory
datadir = [homedir, '\Data\', subcode, '_', p_init,'\'];
% PC % datadir = [homedir, '\Data\', subcode, '_', p_init,'\'];
clear homedir
clear datetag p_init subcode

if ~exist(datadir, 'dir')
    mkdir(datadir);
end


%% Set up experiment

% Load condition order
load('BodyLoc_all_order.mat');

% Cut down to those needed for this sub - 4 blocks per person (e.g., if sub 1 - take first 4 rows)
subconds = all_orders_rand((subnum-1)*4+1:(subnum-1)*4+4,:);
clear all_orders_rand subnum

% Number of trials & blocks
if run_num == 0
    % training
    blocks = 1;
    trials = 3;
else
    % main exp
    blocks = 4; % should be 4
    trials = size(subconds,2); % should be 7
end


%% Set up data saving matrices

% Initialise timing matrix - the extra 2 are for the dead TRs (start & finish)
timings = zeros(6, (trials*2*blocks) + 2*blocks);

% Start counter
c = 0;

% Set rows
row_block = 1; row_trial = 2; row_event = 3; row_TR = 4; row_cumTR = 5; row_toc = 6;

% Loop to add in desired times
for b = 1:blocks
    
    % Get conds for this block
    subcond_block = subconds(b, :);
    
    % Start another counter for trials
    ctr = 0;
    
    for t = 1:trials*2+2
        
        % Add to counter
        c = c + 1;
        
        if t == 1
            % Put dead TRs
            timings(row_TR,c) = TRsdead * TR;
            
            % Add event type
            timings(row_event,c) = 555;
            
        elseif ~mod(t,2) && t ~= trials*2+2
            % Put break times in all EVEN positions
            timings(row_TR,c) = TRsrest * TR;
            
            % Add event type
            timings(row_event,c) = 100;
            
            % Add block num to timing matrix
            timings(row_block,c) = b;
        
        elseif mod(t,2) && t ~=1
            % Put stimulus times in at all ODD positions (except 1)
            timings(row_TR,c) = TRsmove * TR;
            
            % Add to trial counter
            ctr = ctr+1;
            
            % Add event type
            timings(row_event,c) = subcond_block(ctr);
            
            % Add block num and trial num to timing matrix
            timings(row_block,c) = b;
            timings(row_trial,c) = ctr;
            
        elseif t == trials*2+2
            % Put dead TRs
            timings(row_TR,c) = TRsdead * TR;
            
            % Add event type
            timings(row_event,c) = 555;
            
        end
        
        % Add cumulatively
        timings(row_cumTR,c) = sum(timings(row_TR,:));
        
    % end trial loop    
    end
    
    clear subcond_block ctr
    
% end block loop    
end

clear b t c ctr
clear row_block row_trial row_TR

% Save so far
save([datadir, filename]);


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


% % Visuals
% Initialise some set up parameters
PsychDefaultSetup(2);

%Choosing the display
screens=Screen('Screens'); screenNumber=max(screens); clear screens

%Open Screen
[window, windowRect] = PsychImaging('OpenWindow', screenNumber, 255/4); %was 255/2 changed to 255/4
% [window, windowRect]=Screen('OpenWindow', screenNumber,[], [10 20 600 300]); % small debugging window

% Set screen parameters
Screen('TextSize', window, 40); % was 40 12/4

% Set up alpha-blending for smooth (anti-aliased) lines --> fixation cross below wont run without it
Screen('BlendFunction', window, 'GL_SRC_ALPHA', 'GL_ONE_MINUS_SRC_ALPHA');

% Set things up for fixation cross
[xCentre, yCentre] = RectCenter(windowRect); fixCrossDimPix = 40; xCoords = [-fixCrossDimPix fixCrossDimPix 0 0]; yCoords = [0 0 -fixCrossDimPix fixCrossDimPix]; allCoords = [xCoords; yCoords]; clear fixCrossDimPix xCoords yCoords; lineWidthPix = 4;

clear ans


%% General instructions & instruction things

% Instruction
DrawFormattedText(window, sprintf('Please move the body \n part instructed on screen \n for the whole time the \n message is on screen\n\n Please also try to keep \n your head as still as possible \n\n Thank you!'), 'center', 'center', [0 0 0]);
% DrawFormattedText(window, sprintf('Please move the body part instructed on screen \n for the whole time the message is on screen\n\n Please also try to keep your head as still as possible \n\n Thank you!'), 'center', 'center', [0 0 0]);

Screen('Flip', window);

% Wait
WaitSecs(3*TR);
clear ans

% Set generic rest message
msg_rest = sprintf('Please lie still');
% msg_rest = sprintf('Please rest (lie still)');

%% Wait for first trigger then pause for dead TRs

% Say we are waiting (for trigger)
DrawFormattedText(window, sprintf('Waiting for scanner'), 'center', 'center', [0 0 0]);
Screen('Flip', window);

% Wait for trigger
wait_for_trigger

%% set up params for a flicker dot (to manage frequency of movements)
% Define parameters
backgroundCol = [(255/4), (255/4), (255/4)];
dotSize = 80; % Size of the dot in pixels
flickerRate = 1 / TR; % Calculate flicker rate in Hz
dotCol1 = [34 139 34];
dotCol2 = backgroundCol;
screenHeight = windowRect(4); % Height of the screen in pixels
lowerHalfRect = [0 screenHeight/2 windowRect(3) screenHeight]; % Define the rectangle for the lower half of the screen
maxDuration = (TRsmove*TR)-TR;% This seems to be the only way not to add 70ms to the trial time; Max duration of flickering in seconds

%% Event loop - Loop through all timing events in timings mat

% el = 1;
% for el = 1:4
for el = 1:(size(timings,2))

    % Work out what kind of event
    event_type = timings(row_event, el);

    % Do what is needed based on event type
    if event_type == 555
        % % Dead TRs

        % Present fixation
        Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 0], [xCentre yCentre], 2);
        
    elseif event_type == 100
        % % Rest

        % Present move message on screen
        DrawFormattedText(window, msg_rest, 'center', 'center', [0 0 0]);

    elseif ismember(event_type, subconds)
        % % Movement
%         for frames = 1:xx
        % Present move message on screen
%         DrawFormattedText(window, sprintf('Please move your %s', cond_names(event_type)), 'center', 'center', [0 0 0]);
        DrawFormattedText(window, sprintf('%s', cond_names(event_type)), 'center', 'center', [0 0 0]);
        
%         end
        
    else
    end

    % Flip screen to reveal
    Screen('Flip', window);

    % Wait until time elapsed
    WaitSecs('UntilTime', t0 + timings(row_cumTR, el) );
    clear ans
    clear event_type

    % Record actual event time (and start tic timer again)
    timings(row_toc, el) = toc; tic

% End event loop
end

clear t0

% Save data
save([datadir, filename]);

% Finish final timer (time not needed)
toc

% Close psychtoolbox screen
sca

% Re-enable echo to the command line for key presses (CTRL+C to exit)
ListenChar(1);
RestrictKeysForKbCheck([]);

clear allCoords lineWidthPix screenNumber window windowRect xCentre yCentre
clear msg_rest


%% Generating extra timing info needed

% % Get run timing
time.intended = round(sum(timings(row_cumTR,:))/60,4);
time.actual = round(sum(timings(row_toc,:))/60,4);


%% Get stimulus timing files

% Generate fileIDs for each condition
for fi = 1:size(cond_names,1)
    filenames{fi,:} = sprintf('%s%s%s%s%s', datadir, filename, '_timings_', cond_names(fi), '.txt');
end
clear fi

% Open fileIDs
fid1 = fopen(filenames{1}, 'wt');
fid2 = fopen(filenames{2}, 'wt');
fid3 = fopen(filenames{3}, 'wt');
fid4 = fopen(filenames{4}, 'wt');
fid5 = fopen(filenames{5}, 'wt');
fid6 = fopen(filenames{6}, 'wt');
fid7 = fopen(filenames{7}, 'wt');

% Run loop to extract timngs for each condition
for s = 1:size(timings,2)
    
    if timings(row_event,s) == 1
        fprintf(fid1, [num2str(timings(row_cumTR,s)) ' '] );
    elseif timings(row_event,s) == 2
        fprintf(fid2, [num2str(timings(row_cumTR,s)) ' '] );
    elseif timings(row_event,s) == 3
        fprintf(fid3, [num2str(timings(row_cumTR,s)) ' '] );
    elseif timings(row_event,s) == 4
        fprintf(fid4, [num2str(timings(row_cumTR,s)) ' '] );
    elseif timings(row_event,s) == 5
        fprintf(fid5, [num2str(timings(row_cumTR,s)) ' '] );
    elseif timings(row_event,s) == 6
        fprintf(fid6, [num2str(timings(row_cumTR,s)) ' '] );
    elseif timings(row_event,s) == 7
        fprintf(fid7, [num2str(timings(row_cumTR,s)) ' '] );
    end
    
end
clear s

fclose(fid1); fclose(fid2); fclose(fid3); fclose(fid4); fclose(fid5); fclose(fid6); fclose(fid7);
clear fid1 fid2 fid3 fid4 fid5 fid6 fid7
clear filenames

clear row_block row_cumTR row_event row_toc row_TR row_trial
clear ans


%% Final save

% Save
save([datadir, filename]);

