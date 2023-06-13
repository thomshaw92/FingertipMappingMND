
% This script has been checked by HDJ on 01/07/22 to ensure that if you put the tactors in the order specified at the start (this order varies by participant number)
% curr_fing = 1 plays on left middle (in foam position LCR)
% curr_fing = 2 plays on left index (in foam position LR)
% curr_fing = 3 plays on right index (in foam position RL)
% curr_fing = 4 plays on right middle (in foam position RCL)


%% Clean up
close all;
clearvars;
sca;

% turn off sci notation
format short g

% Make sure any old audio stuff is closed
PsychPortAudio('Close');


%% Start timer for experimental duration
tic


%% General details

dets.psychvis = 1; % visual display
dets.keylock = 0; % lock the keyboard while experiment is on so you can't type anything other than specified keys
dets.figs = 1; % 1 = pop figures on screen for performance at the end; 0 = dont
dets.saveoutput = 1; % 0 = dont save
dets.response_yes = 1; % 0 = don't collect responses - for use in psychvis 0 (for the moment) only to allow debugging
dets.shuffle_trials = 1; % 1 = shuffle; 0 = don't
dets.fit_type = 1; % 1 = logit reg; 2 = (don't use) Weibull
dets.output_by_fing = 1; % [GETS RESET TO 0 LATER FOR PRACTICE AND TRAIN] 1 = split output for each finger tested; 0 = collapses over fingers tested

% Set threshold level to use for curve fitting (proportion) - currently set for Weibull fitting only
thresh.value = .75;


%% Experimenter input section

% participant details
% p_init = 'HDJ'; % Manually enter for piloting
p_init = input('Participant Intitials: ', 's');
% subnum = 1;
subnum = input('SUBJECT Number: ');
if subnum < 10
     subcode = ['P00' num2str(subnum)];
else
     subcode = ['P0' num2str(subnum)];
end

% Type of session
% testtrainQ = 1; % 1 = testing; 2 = training
testtrainQ = input('Testing or training? Testing = 1, training = 2: ');

% Which test/training?
if testtrainQ == 1
    % % test
    % test_no = 1;
    test_no = input('Which number testing session is this? 1/2: ');
elseif testtrainQ == 2
    % % train
    % train_no = 1;
    train_no = input('Which number training session is this? 1/2/3/4: ');
else
end

% Experimental or practice
% maintrialsQ = 0; % 1 = experimental (main) trials; 0 = practice
maintrialsQ = input('Experimental or practice trials? Experimental = 1, practice = 0: ');


%% Script determines extra participant settings

% Where relevant - resets dets variable from above that splits output by finger
if testtrainQ == 1 && maintrialsQ == 1
    % Do nothing - leave as above
else
    dets.output_by_fing = 0;
end

% Set up how many fingers being used/ which hands - Hands should always be BOTH for testing, and LEFT for training
if testtrainQ == 1
    num_fings = 4; % testing 4 fingers
    hand = 3; % 1 = left; 2 = right; 3 = BOTH***
elseif testtrainQ == 2
    num_fings = 1; % training one finger
    hand = 1; % 1 = LEFT***; 2 = right
end

% Get hand name
if hand == 1
    hand_name_short = 'LEFT';
    hand_instruct = 'your LEFT hand';
elseif hand == 2
%     % I set this up but we aren't using it - so commented out
%     hand_name_short = 'RIGHT';      
%     hand_instruct = 'your RIGHT hand';
elseif hand == 3
    hand_name_short = 'BOTH';
    hand_instruct = 'BOTH hands';
end

% Get identity of fingers based on num fings above and which hand(s)
if num_fings == 1
    % One finger - use middle (left middle, as left hand set above)
    fing = 1; % 070722 - fing 1 = curr_fing 1 = left middle (to be used for training)
    fing_instruct = 'MIDDLE finger';
    fing_name_short = 'M';
elseif num_fings == 4 && hand < 3
    % I set this up but we aren't using it - so commented out
%     fing = 1:4;
%     fing_instruct = 'Index, middle, ring and little fingers';
%     fing_name_short = 'IMRL';
elseif num_fings == 4 && hand == 3
    % Two fingers on either hand - use index and middle
    fing = 1:2;
    fing_instruct = 'INDEX and MIDDLE fingers';
    fing_name_short = 'IM';
else
end


% Date tag
clockdata = clock;
clockdata = clockdata(1:5);
datetag = sprintf('%d_%d_%d_%d_%d',clockdata); 
clear clockdata

% Build filename
filename = [datetag, '_', subcode, '_', p_init, '-', 'VibroLearn_', 'hand', hand_name_short, '_fings', fing_name_short];
clear fing_name_short hand_name_short

% Build sub - used later for title of figure
sub = [subcode ' ' p_init];

% Add test type to filename
if testtrainQ == 1
    filename = [filename, '_test', num2str(test_no)];
else
    filename = [filename, '_train', num2str(train_no)];
end

% Add practice to filename (if relevant)
if maintrialsQ == 0
    filename = [filename, '_practice'];
else
end

% Set number of channels - WONT EVER CHANGE
num_chans = 6;


%% Pop filename on screen so experimenter can check participant dets and cancel out if details are wrong

input(sprintf('Check participant dets: %s - exit if incorrect', filename));
clear ans


%% Make dir for that participant in Data dir if it doesn't exist already

datadir = [pwd, '\Data\Learning_experiment\', subcode, '_', p_init,'\'];

if ~exist(datadir, 'dir')
    mkdir(datadir);
end


%% Get tactor order and pop on screen for checking

% Load orders
load('C:\Users\uqhdemp1\Desktop\Hons_testing_2022_HDJ\tac_combos.mat');
clear tac_combos

% Get order for that participant based on their participant number
tac_order = tac_order_mat(subnum, 3:6);
clear tac_order_mat

% Pop tactor order on screen to be checked
input(sprintf('place tactors in the order (from left to right): %d %d %d %d - press enter once this is done', tac_order));


%% If training - get training dif levels OR if second test - get test levels from first test

% If training - need to get training levels
if testtrainQ == 2 || (testtrainQ == 1 && test_no == 2)
    
    % Training only: Clear thresh var in training as we are not using it (not curve fitting)
    if testtrainQ == 2
        clear thresh
    else
    end
    
    % load data from the right previous session
    load_prev_data
    
    % Pop details from last sess and levels on screen so experimenter can check they are what they were expecting
    if testtrainQ == 2
        if train_no == 1
            input( sprintf('Check thresh: %.3f (%.2f) and training levels: %.2f %.2f %.2f %.2f - exit if incorrect', thresh_from_prev_sess, closest_dif_level_from_prev_sess, dif_levels) );
        else
           input( sprintf('Check last train levels: %.2f %.2f %.2f %.2f vs change (%d) and new train levels: %.2f %.2f %.2f %.2f - exit if incorrect', dif_levels_last, change_last, dif_levels) ); 
        end
    else
        input( sprintf('Check testing levels: %.2f %.2f %.2f %.2f %.2f - exit if incorrect', dif_levels) );
    end
    
else
end

clear change_last dif_levels_last
clear closest_dif_level_from_prev_sess thresh_from_prev_sess
clear subcode p_init subnum


%% Make sounds

% General sound settings
amp = 1;
Fs = 48000;
dur = .25; % in seconds
time = (1 : dur * Fs);
phase = 0; % phase shift - we aren't using this so set to 0
freq = 30; % base frequency - flutter range

% % Get difficulty levels all and dif levels - if first test
if testtrainQ == 1
    if test_no == 1
        % TESTING: using small number of difficulties (e.g., 4) but considering standard first as different trials to comparison first, so you end up with double the levels (e.g., 8) - this allows scoring 0-1 and use of logistic regression curves for fitting
        levels(1,1) = 5; % test - must be even
        levels(2,1) = levels(1,1)*2; % train - must be even - made it more levels so you have more difficulties to fit around threshold
        levels(3,1) = 1; % Practice - must also be even. This is not an even number, but adds one on below to make 2 - so is even. 

        % Get perc increments
        for p_i = 1:3

            % Use no. of levels (above) to calc full range of levels to be tested
            perc_increments{p_i,:} = linspace(0.5,10, levels(p_i,1));
            % changed to make harder from this on 010722 (lowest value now 0.5 not 1) % perc_increments{p_i,:} = linspace(1,10, levels(p_i,1));

        end
        clear p_i levels

        % Add another really easy level if practice
        perc_increments{3,:} = [perc_increments{3,:} perc_increments{3,1}+10];
        perc_increments{3,:} = flip(perc_increments{3,:},2);

        % Add increments to base frequency
        for in = 1:3
            % get the right values
            perc_increments_i = perc_increments{in,:};

            % Add base freq onto them
            dif_levels_all{in,:} = freq+perc_increments_i; % Will make more s shaped later - fit to a cumulative gaussian

            clear perc_increments_i
        end
        clear in perc_increments

% end if first train Q
    else
    end
else
end

% Extract dif levels for this version of the experiment (test only - experimental vs. practice, train levels determined by later test1 (then trainings) from these base train levels set here)
if testtrainQ == 1
    if maintrialsQ == 1
        dif_levels = dif_levels_all{1,:};
    else
        dif_levels = dif_levels_all{3,:};
    end
else
end

% Make sounds - NOTE THIS SCRIPT EXPECTS THAT YOU HAVE MOVED THE TACTORS INTO THE POSITION SPECIFIED BY TAC_ORDER - I.E. DIFFERENT FOR EACH PARTICIPANT
% IT ALSO ONLY WORKS FOR BOTH HANDS I/M
make_sound_tac_order_varied_160622


%% Set up trial/block details

% Repetition settings TO BE CHANGED LATER - setting the duration of the experiment
% NOTE: NONE OF THE BELOW CREATE PROPER PARAMETRIC DESIGN WITH MORE THAN 1 FINGER (NUM_FING>1 I.E. IN TESTING) UNLESS FINAL N OF TRIALS = 16 OR MORE
if maintrialsQ == 1
    % Experimental trials
    if testtrainQ == 1
        % Testing
        trials = 10; % 10*2 = 20 of each difficulty (10 either direection - first/ second faster) * 5 dif levels = 100 trials/ finger * 4 fings = 400 trials for test
        trials = trials * 2; % double the number of trials (so we have half one direction (comparison first) and half the other way)
    else
        % Training
        trials = 160; % MINIMUM 2/ must be EVEN to work; 160*4 dif levels
    end

    trials = trials * size(dif_levels,2); % per finger
    trials = trials * num_fings; % total trials
    
    % Blocks
    blocks = 4; % we might want more so they get more regular feedback in training for motivation
else
    % Practice trials
    trials = 2; % won't make properly parametric design in TESTS (4 fingers) unless this number is 4, but we have accounted for this below and its not important for practice
    trials = trials * num_fings;
    
    % Add more trials for training - as the above only gives 2 trials and this does not work below as there are less trials than dif levels (4) - so has to be minimum 4
    if testtrainQ == 2
        trials = trials * size(dif_levels,2); % bring above to number of dif_levels (needs to be +8 for faster trials generation to work)
    else
    end
    
    % Blocks
    blocks = 1;
end

% Work out where breaks will be if multiple blocks
if blocks > 1
    trial_breaks = round(trials/blocks,0);

    for b = 1:(blocks-1)
        trial_breaks(1,b+1) = round((trials/blocks)*(b+1),0);
    end
    
    % Replace the last cell with final trial (should be this anyway, but just in case)
    trial_breaks(1,blocks) = trials;
else
end

clear b


%% Generate trial mat

% Set up trial matrix to record performance
trial_mat = zeros(trials, 11)+999;

% Generate base difficulty types from dif levels
types_dif = repmat(dif_levels, 1, trials/size(dif_levels,2))';

% Get fing types (and hand types for some conditions where hand is always the same)
% if num_fings == 1
%     types_fing = (zeros(1, trials ) + fing)';
% elseif num_fings == 4 && hand < 3
%     % Made this but not using - so commented out
% %    types_fing = repmat(1:(num_fings), 1, (trials/num_fings) )';
% elseif num_fings == 4 && hand == 3
%     types_fing = repmat(fing, 1, (trials/size(fing,2)) )';
% else
% end

% Sort finger types
% types_fing = sort(types_fing,1);

% Get hand types (for two hand experiments) - has to be done in complicated way to ensure equal hand distribution between finger types
% if hand == 3
%     % Two hands
%     types_hand = [];
%     for th = 1:size(fing,2)
%         types_hand_add = repmat(1:2, 1, trials/2/size(fing,2))';
%         types_hand_add = sort(types_hand_add,1);
%         types_hand = [types_hand; types_hand_add];
%         clear types_hand_add
%     end
% else
%     % One hand only
%     types_hand = (zeros(1, trials ) + hand)';
% end
% clear th

% Get tactor types
if hand == 3
    % If both hand - make new sound types vector
    types_tactor = repmat(1:num_fings, 1, trials/num_fings)';
    types_tactor = sort(types_tactor,1);
else
    % If one hand - vary based on hand
    if hand == 1
        types_tactor = (zeros(1, trials ) + fing)';
        % types_tactor = types_fing;
    elseif hand == 2
        % Commented this out as don't want it to get used
%         if fing == 1
%             tactor = 3;
%         else
%         end
%         types_tactor = (zeros(1, trials ) + tactor)';
%         clear tactor
    end
end

% Add in which is faster 1st (1) or 2nd (2) - this allows you to make sure it's evenly distributed between the two for TESTING, which the randomise was not doing
% (not important for training that we have exactly half first for all combinations of dif_levels/fing_types, just need about half trials either way to prevent guessing)
% As above, needs to be done in a slightly complicated way ''
types_faster = [];
for tf = 1:trials/2/size(dif_levels,2)
    types_faster_add = repmat(1:2, 1, size(dif_levels,2) )';
    types_faster_add = sort(types_faster_add,1);
    types_faster = [types_faster; types_faster_add];
    clear types_faster_add
end
clear tf


% Randomise things for trial mat - faster_types does not get randomised as done above
if dets.shuffle_trials == 1
    if maintrialsQ == 1
        % % Experimental trials
        % Get random numbers to randomise order
        order = 1:size(types_dif,1);
        order = order(randperm(length(order)));

    else
        % % Practice trials - this maybe should only be this way for testing, but its not having a bad effect in training, so leaving it
        % Create order to sort - easiest first and harder ones last (starts with harder ones)
        nums = 1:trials;
        % Get odd and even trial numbers (this will collect the easy and
        % hard trials)
        order_harder = nums(rem(nums,2)==1);
        order_easier = nums(rem(nums,2)~=1);
        clear nums
        
        % Shuffle them within odds and evens (this will mean they are presented in a random order - but still easy first, then hard because of they way we horizontally concatenate them in next step)
        order_harder = order_harder(randperm(length(order_harder)));
        order_easier = order_easier(randperm(length(order_easier)));
        
        order = [order_harder, order_easier];
        clear order_harder order_easier
    end
    
    % Shuffle other variables by order
    types_dif = types_dif(order);
    types_faster = types_faster(order);
    % types_fing = types_fing(order);
    % types_hand = types_hand(order);
    types_tactor = types_tactor(order);
    clear order
    
else
end

% % Extra shuffle for practice fasters (even when not shuffling trials)
% % DONT THINK I ACTUALLY NEED THIS ANYMORE AS SHUFFLED ABOVE
% if maintrialsQ == 0 && testtrainQ == 1
%     % Randomly shuffle which is faster - this is a hack to get a bit more randomness as the above does not generate a properly parametric design as we don't have enough trials in practice (for testing)
%     % Also edited so does half at a time so you dont end up with all the 1's first and 2's second and get no trials of some types - which messes up dif_mat
%     % shuffles all together, dont use % types_faster = types_faster(randperm(length(types_faster)));
%     types_faster1 = types_faster(1:trials/2);
%     types_faster2 = types_faster((trials/2)+1:end);
% 
%     types_faster1 = types_faster1(randperm(length(types_faster1)));
%     types_faster2 = types_faster2(randperm(length(types_faster2)));
%     types_faster = [types_faster1; types_faster2];
% else
% end


% Extra stuff for practice
if maintrialsQ == 0
    if dets.shuffle_trials == 1 && testtrainQ == 1
        % Get real trial location - practice only TEST
        real_trial = ischange(types_dif);
        real_trial = find(real_trial==1);
        real_trial = real_trial-1;
    else
        real_trial = 3;
        % real_trial = trials/2;
    end
else
end


% Add to trial_mat
row_dif = 3; row_hand = 4; row_fing = 5; row_tactor = 6; row_faster = 7; 
trial_mat(:,row_dif) = types_dif;
% trial_mat(:,row_hand) = types_hand;
% trial_mat(:,row_fing) = types_fing;
trial_mat(:,row_tactor) = types_tactor;
trial_mat(:,row_faster) = types_faster;
clear types_dif types_faster types_hand types_fing types_sound types_tactor
    

%% Initialise psychtoolbox

% % Audio
InitializePsychSound(1); %inidializes sound driver...the 1 pushes for low latency

% Initialise two sound buffers for the two sounds
pahandle = PsychPortAudio('Open', [], [], 2, Fs, num_chans, 0); % for the first played sound
% pahandle2 = PsychPortAudio('Open', [], [], 2, Fs, num_chans, 0); % for the second played sound

% play test sound - load into buffer then test pahandle 1 then 2
PsychPortAudio('FillBuffer', pahandle, x1{1,:}); PsychPortAudio('Start', pahandle, 1, 0);
WaitSecs(dur);
PsychPortAudio('FillBuffer', pahandle, x4{1,:}); PsychPortAudio('Start', pahandle, 1, 0);
% PsychPortAudio('FillBuffer', pahandle1, x1{1,:}); PsychPortAudio('Start', pahandle1, 1, 0);
% PsychPortAudio('FillBuffer', pahandle2, x4{1,:}); PsychPortAudio('Start', pahandle2, 1, 0);
WaitSecs(dur+2)


% % Keyboard
% improve portability of your code across operating systems 
KbName('UnifyKeyNames');

% Disabling keyboard input to Matlab
ListenChar(2); 

clear ans


if dets.psychvis == 1
    % % Visual
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

% end of psychtool loop
else
end


% Set up key lock if wanted
if dets.keylock == 1
    
    % Set keys to allow responses from (only enacted later on, at resp)
    % WILL NEED TO CHECK THE NAME OF THE ENTER/ RETURN BUTTON
    % activeKeys = [97 98 99 100 101];
    activeKeys = [KbName('1') KbName('2') KbName('f') KbName('j') KbName('return')];

    % Restrict inputs to just keys we want (defined at top)
    RestrictKeysForKbCheck(activeKeys);

    % Suppress echo to the command line for keypresses (exit with CTRL+C)
    ListenChar(2);
else
end


%% General instructions

if maintrialsQ == 0
    if dets.psychvis == 1
        for il = 1:2
            
            % General instructions settings
            Screen('TextSize', window, 40);
        
            if il == 1
                % First instruction - put hands/ fingers on tactors
                DrawFormattedText(window, sprintf('Place the %s of %s on the tactors as instructed, \n and place your feet on the foot pedals. \n \n Press one of the foot pedals when you are ready to continue', fing_instruct, hand_instruct), 'center', 'center', [0 0 0]);
                Screen('Flip', window);
            else
                % Second instruction - task
                DrawFormattedText(window, sprintf('On each trial, you will feel two pulses. One will be faster and one slower. \n Your task is to identify which pulse was faster. \n \n Respond with the left-most pedal if the faster one was presented first \n and respond with the right-most if it was second. \n \n Try to be as accurate as you can. \n If you are unsure, take your best guess.\n \n When you are ready, press one of the foot pedals to begin the experiment...'), 'center', 'center', [0 0 0]);
                Screen('Flip', window);
            end
                    
            % % Wait for enter
            % Timeout boolean
            timedout_i = false;
    
            while ~timedout_i
                % Check if a key is pressed
                [ keyIsDown, ~, ~ ] = KbCheck(-1); 
                if(keyIsDown), break; end
            end
            clear keyIsDown timedout_i il
            clear ans
    
            % Pause
            WaitSecs(1);
        end
        
    else
    end
else
    % % Wait for enter
    % Timeout boolean
    timedout_i = false;

    while ~timedout_i
        % Check if a key is pressed
        [ keyIsDown, ~, ~ ] = KbCheck(-1); 
        if(keyIsDown), break; end
    end
    clear keyIsDown timedout_i il
    clear ans

    % Pause
    WaitSecs(2);
end

%% Trial loop

% Start trial counter at ZERO always
c = 0;

% Set block to 1 - this will get changed at trial breaks later
block = 1;

% Initialise counters
counter_cor = [];
counter_trials = 0;
perc_cor_block = [];


% trial = 1;
for trial = 1:size(trial_mat,1)

    % Put up instructions if training (certain trials), or fixation cross if not
    if dets.psychvis == 1
        if maintrialsQ == 0 && c == real_trial
            % Let participants know their training trials are starting (no feedback)
            Screen('TextSize', window, 40);
            DrawFormattedText(window, sprintf('Real training trials beginning'), 'center', 'center', [0 0 0]);
            Screen('Flip', window);
            WaitSecs(3);
        else
        end

        % Redraw black fixation
        Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 0], [xCentre yCentre], 2);
        Screen('Flip', window);
    else
    end

    % Get difficulty level & pair for this trial
    c = c+1;
    curr_diff = trial_mat(c,row_dif);
    curr_tactor = trial_mat(c,row_tactor);
    curr_faster = trial_mat(c,row_faster);


    %% Get sounds - for the right finger(s)

    % Get appropriate matrix of sounds for this finger (all frequencies)
    sound_trial = eval(sprintf('x%d', curr_tactor));

    % Get the standard frequency sound for this finger
    sound_standard = sound_trial{1,:};

    % Work out which position the comparison sound is in
    comp_pos = find(dif_levels == curr_diff)+1;

    % Get comparison sound
    sound_comp = sound_trial{comp_pos, :};
    clear comp_pos sound_trial


    %% Organise sounds

    % Put standard freq and comparison freq for this trial into a matrix
    sound_order = [freq curr_diff];
    
    % Pre-determined which will be faster (so its half/half exactly)
    if curr_faster == 1
        % flip order
        sound_order = flip(sound_order,2);
        
        % Comparison (faster sound) is sound 1
        playsound1 = sound_comp;
        playsound2 = sound_standard;
        order_message = 'first (press 1)';
    else
        % do not flip - leave as is
        
        % Comparison (faster sound) is sound 2
        playsound1 = sound_standard;
        playsound2 = sound_comp;
        order_message = 'second (press 2)';
    end

    clear sound_standard sound_comp


    % If training (and not real trials) - show on screen freq of taps
    if maintrialsQ == 0 && c <= real_trial
        if dets.psychvis == 1 
            % Show order message
            Screen('TextSize', window, 40);
            DrawFormattedText(window, sprintf('Training trial (with answer): Which was faster?\n\n answer = %s', order_message), 'center', 'center', [0 0 0]);
            Screen('Flip', window);

            % Pause
            WaitSecs(2);

        else
        end
    else
    end

    clear order_message


    %% Play sound - not in a loop, to reduce processing time between sounds for accuracy

    % Load into buffer
    PsychPortAudio('FillBuffer', pahandle, playsound1);
    % PsychPortAudio('FillBuffer', pahandle1, playsound1); PsychPortAudio('FillBuffer', pahandle2, playsound2);

    % Play sound 1
    PsychPortAudio('Start', pahandle, 1, 0);

    % Pause length of sound (dur) so it completes, then pause twice that time again for an actual gap between sounds
    WaitSecs(dur+ (dur*2));

    % Load second sound into buffer
    PsychPortAudio('FillBuffer', pahandle, playsound2);

    % Play sound 2
    PsychPortAudio('Start', pahandle, 1, 0);

    % Pause so sound completes
    WaitSecs(dur);

    % Start time counter for RT
    % t1 = GetSecs; tic

    clear playsound1 playsound2


    %% Get response

    % Initialise resp to blank
    resp = [];

    % Set question
    question = ('Which was faster? First sound (press left pedal) or second sound (press right pedal): ');

    if dets.psychvis == 0
        if dets.response_yes == 1
            resp = input(question, 's');
        else
        end
    else
        Screen('TextSize', window, 40);
        DrawFormattedText(window, sprintf(question), 'center', 'center', [0 0 0]);
        Screen('Flip', window);

        % Timeout boolean
        timedout_r = false;

        while ~timedout_r
            % Check if a key is pressed
            [ keyIsDown, ~, keyCode ] = KbCheck(-1); % this -1 queries all keyboards and returns merged input - does not pick up extra footpedal keyboard without this -1
            % [ keyIsDown, ~, keyCode ] = KbCheck; % if you want to include RT you need keyTime: [ keyIsDown, keyTime, keyCode ] = KbCheck; 
            if(keyIsDown), break; end
        end

        % Store key pressed
        if(~timedout_r)
            resp = KbName(keyCode);
        end

        clear respd keyCode keyIsDown timedout_r

    % psychtool end    
    end
    clear question

    % Edit cell responses - just take first value of cell and make it not a cell
    if iscell(resp)
        resp = resp{1};
        resp = num2str(resp);
    else
    end

    % Fix weird resps - change resp to 0 if wrong
    if isempty(resp) || iscell(resp) || size(resp,2) ~= 1
        resp = 0;
    else
    end

    % Fix resp from string to number 1/2
    if resp == '1'
        resp = 1;
    elseif resp == 'a'
        resp = 1;
    elseif resp == '2'
        resp = 2;
    elseif resp == 'b'
        resp = 2;
    else
        resp = 0;
    end

    % Check if correct
    if curr_faster == 1 && resp == 1
        cor = 1;
    elseif curr_faster == 2 && resp == 2
        cor = 1;
    else
        cor = 0;
    end

    % Generate feedback
    if cor == 1
        feedback = ('Correct');
        % feedcol = [0 1 0];
        feedcol = [0.4660 0.6740 0.1880]; % dark green
    else
        feedback = ('Incorrect');
        feedcol = [1 0 0];
        % feedcol = [0.6350 0.0780 0.1840]; % dark red
    end
    
    % Work out whether to display trial feedback
    if testtrainQ == 2
        % Training
        trial_feed = 1;
    elseif testtrainQ == 1 && maintrialsQ == 0
        % Test - practice
        trial_feed = 1;
    else
        trial_feed = 0;
    end
    
    % Display trial feedback
    if trial_feed == 1
        if dets.psychvis == 0
            if response_yes == 1
                input([feedback ' - press footpedal to continue'], 's');
            else
            end
        else
            Screen('TextSize', window, 40);
            DrawFormattedText(window, sprintf(feedback), 'center', 'center', feedcol);
            Screen('Flip', window);
        end
    else
    end

    clear ans feedcol feedback trial_feed
    clear curr_diff curr_tactor curr_faster


    %% Add to trial matrix & save
    row_resp = 10; row_cor = 11;
    trial_mat(c,1) = block;
    trial_mat(c,2) = trial;
   % PASTED FROM ABOVE: row_dif = 3; row_hand = 4; row_fing = 5; row_tactor = 6; row_faster = 7;
    trial_mat(c,8) = sound_order(1);
    trial_mat(c,9) = sound_order(2);
    trial_mat(c,row_resp) = resp;
    trial_mat(c,row_cor) = cor;
    
    % Add to counters for this block
    counter_cor = [counter_cor cor];
    counter_trials = counter_trials + 1;

    clear cor resp sound_order qprop

    % Save
    if dets.saveoutput == 1
        save([datadir,filename]);
    else
    end

    % Pause between trials
    WaitSecs(1);


%% Pause at end of blocks
    if maintrialsQ == 1
        if ismember(trial, trial_breaks)
            
            % Calculate perc corr
            perc_cor_block = [perc_cor_block, ( sum(counter_cor)/sum(counter_trials) )*100];
            
            
            % Present end of block feedback
            if trial == trials
                feedback_end = sprintf('End of experiment. Great job! \n\n Your last block score = %d percent \n Your best score so far = %d percent \n\n Press footpedal to exit', round(perc_cor_block(end),0), round(max(perc_cor_block),0) );
            else
                feedback_end = sprintf('End of block %d (from %d). Great job! \n\n Your last block score = %d percent \n Your best score so far = %d percent \n\n Press footpedal when you are ready to go on', block, blocks, round(perc_cor_block(end),0), round(max(perc_cor_block),0) );
            end

            if dets.psychvis == 0
               input(feedback_end, 's');
            else
                Screen('TextSize', window, 40);
                DrawFormattedText(window, sprintf(feedback_end), 'center', 'center', [0 0 0]);
                Screen('Flip', window);

                % Timeout boolean
                timedout_b = false;

                while ~timedout_b
                    % Check if a key is pressed
                    [ keyIsDown, ~, ~ ] = KbCheck(-1); 
                    if(keyIsDown), break; end
                end

                clear keyIsDown feedback_end timedout_b
                clear feedback_end

            end
            
            WaitSecs(2);
            
            % Change block number
            block = block + 1;
            
            % Reset counters
            counter_cor = [];
            counter_trials = 0;
            
        else
        end
    else
        if trial == trials
            % Calculate perc corr
            perc_cor_block = [perc_cor_block, ( sum(counter_cor)/sum(counter_trials) )*100];
        else
        end
    end
    
    
% end trial loop
end

clear block trial
clear x1 x2 x3 x4
clear pahandle1 pahandle2
clear ans
clear counter_cor counter_trials

% Undo psychtoolbox stuff - where applicable
if dets.keylock == 1
    % Reset the keyboard input checking for all keys (place out of loop)
    RestrictKeysForKbCheck;

    % Re-enable echo to the command line for key presses (CTRL+C to exit)
    ListenChar(1)
else
end

% Clear the screen visuals if relevant
if dets.psychvis == 1
    sca
else
end

% Re-enable keypresses to matlab
ListenChar(0);

clear keylock psychtool trainQ screenNumber lineWidthPix window windowRect xCentre yCentre allCoords
clear ans

% Save
if dets.saveoutput == 1
    save([datadir,filename]);
else
end


%% AT END - Score data

if c == trials
    
    % Re add for debugging: row_dif = 3; row_hand = 4; row_fing = 5; row_tactor = 6; row_faster = 7; row_resp = 10; row_cor = 11;
    % Also re-add a sub and datetag: sub = 'P001 JR'; datetag = 010722;

    % Determine how many times we need to do scoring/ plotting - depending on whether output is bring split by finger or not
    % Re add for debugging % dets.output_by_fing = 1;
    if dets.output_by_fing == 1
        scoreplot_reps = num_fings+1;
    else
        scoreplot_reps = 1;
    end

    % Score data
    score_prop_data
    
    clear row_fing row_dif row_faster row_cor row_resp row_hand row_tactor
    
    if dets.saveoutput == 1
        save([datadir,filename]);
    else
    end
    
    % Loop for however many times we need to score/ plot/ fit (where applicable)
    for sr2 = 1:scoreplot_reps
        
    % get dif_mat for that loop
    dif_mat = dif_mats{sr2};
    
        %% Plot outcome
        if dets.figs == 1
            if testtrainQ == 1 && maintrialsQ == 1 
                % Plot "prop faster" - use in testing
                figure(sr2)
                scatter(dif_mat(3,:), dif_mat(8,:), 'r*'); % logged ratio of difference between standard and comparison
                % scatter(1:size(dif_mat,2), dif_mat(8,:), 'r*'); % artificially using 1-8 as x-axis
                ylabel('Proportion "first faster"')
                xlabel('Ratio of standard & comparison stimulus (log)')
                % xticklabels(combined_name_label) - does not work (doesn't align with data points but tick marks, so is not what we need AND needs to be reversed to plot anyway as positive ratios (e.g.40/30) go to the left automatically on matlab, where they need to be right for the way the labels are mapped out
                ylim([0 1])
                grid on
                set(gca,'fontsize',14)
            else
                % Plot "Prop corr" - use in training & practices (no curve fitting)
                figure(sr2)
                scatter(dif_mat(3,:), dif_mat(6,:), 'b*'); % logged ratio of difference between standard and comparison
                % scatter(1:size(dif_mat,2), dif_mat(8,:), 'r*'); % artificially using 1-8 as x-axis
                ylabel('Proportion correct')
                xlabel('Ratio of standard & comparison stimulus (log)')
                ylim([0 1])
                grid on
                set(gca,'fontsize',14)
            end

            % % Get accuracy message & add to plot
            % Get loc to put message
            if testtrainQ == 1
                loc = dif_mat(3,end);
            else
                loc = dif_mat(3,1);
            end
   
            % Get acc
            %  old - only gets acc for all trials - acc_plot = mean(perc_cor_block);
            if sr2 < 5 && maintrialsQ == 1
                corrs = trial_mat(trial_mat(:,6) == sr2, 11);
            else
                corrs = trial_mat(:, 11);
            end

            acc_sr2s(1,sr2) = ( sum(corrs)/size(corrs,1) ) *100;
            clear corrs

            % Get message and add
            txt_tr = sprintf('Mean Acc = %.2f', acc_sr2s(sr2));
            text(loc, 0.15, txt_tr,'FontSize',14)
            clear txt_tr loc
        else
        end


        %% Fit function, get training levels from threshold

        % Testing only (not practice)
        if testtrainQ == 1 && maintrialsQ == 1

            % % Get vars needed - calling them the same as in orig scripts for continuity
            dataStims = dif_mat(3,:);
            dataProp = dif_mat(8,:); % Prop faster
            % dataProp = dif_mat(6,:); % Prop corr - don't use (used by Weibull)
            dataResp = dif_mat(7,:); % Prop faster (used by logit reg)
            dataCount = dif_mat(4,:);

            % Create extended version of dataStims (more values) so can fit a smooth curve
            dataStims_long = linspace(dataStims(1), dataStims(end), 1000);

            % Initialise empty var for params (then if not filled we know of curve fitting issue)
            params = [];

            % Set curve fit error to 0 - changes below if needed
            curve_fit_error(sr2,1) = 0;

            % % Fit function
            if dets.fit_type == 1
                % % Fit logistic regression
                fit_logit_reg
                fit_name = 'logit reg';
            elseif dets.fit_type == 2
                % Fit Weibull function (can deal with prop corr data i.e., 0.5-1 format)
                % MIGHT WANT TO CHANGE STARTING VALUES ONCE WE HAVE SET THE ACTUAL STIM DIFFICULTIES AND DONE SOME PILOTING I.E., ONCE WE KNOW TYPICAL STARTING LEVELS
                fit_Weibull
                fit_name = 'Weibull';
            else
            end

            % % If curve fitting works, do next step, otherwise do back up        
            if isempty(params)
                % Change var & make warning
                curve_fit_error(sr2,1) = 1;
                WARN.curve_fitting = 'Params empty - curve fitting did not work';

                % Interpolating between data points
                curve(sr2,:) = interp1(dataProp, 1:8);
                curve_range(sr2,:) = curve;
            else
            end

            % Curve fitting worked: Plot and calc extra wanted things and add to figure
            plot_thresh_R2
            clear dataStims dataStims_long dataProp dataCount dataResp

            % % Get training levels
            if test_no == 1
                get_train_levels_from_test1
            else
            end
            clear test_name
            
        % end if testrainQ is 1 and maintrialsQ is 1 loop (for fitting)   
        else
        end
       
        
        % Save image
        if dets.saveoutput == 1
            % Generate name to save figure
            if testtrainQ == 1 && maintrialsQ == 1
                titlef = sprintf([num2str(datetag), ' - ', sub, ' - Test ', num2str(test_no), ' - ', fit_name, ' fit']);
            elseif testtrainQ == 1 && maintrialsQ == 0
                titlef = sprintf([num2str(datetag), ' - ', sub, ' - Test ', num2str(test_no)]);
            elseif testtrainQ == 2
                titlef = sprintf([num2str(datetag), ' - ', sub, ' - Train ', num2str(train_no)]);
            end
            
            % Add tactor number to save name where relevant
            if dets.output_by_fing == 1
                titlef = [titlef, ' - ' testnameadd];
            else
            end
            
            % Add practice where relevant and .bmp
            if maintrialsQ == 0
                titlef = [titlef ' practice.bmp'];
            else
                titlef = [titlef '.bmp'];
            end

            % Save image
            saveas(gcf, [datadir, (titlef)]);
            clear titlef
        else
        end
        
        
        % Make struct for all loops of these vars if they exist
        if exist ('params', 'var')
            params_all(sr2,1:2) = params;
        else
        end
        
        if exist ('WARN', 'var')
            WARN_all{sr2,1} = WARN;
        else
        end
        clear params WARN
        
        clear dif_mat
        
    % end sr2 loop for number of scoring and plotting repeats
    end
    
    clear sub datetag scoreplot_reps sr2
    
    
    %% Get training levels for next training
    
    if testtrainQ == 2 && maintrialsQ == 1
        if train_no ~= 4
            % If training is 4 (last) we don't need to recalc levels for next session
            get_train_levels_from_train
        else
            % If is training 1 - do nothing as we already have the train dif levels - calc'd from thresh in above step
        end
    else
    end
    
% end of is trials finished loop
end


%% Get experimental duration
experimental_duration = toc/60;


%% Final save
if dets.saveoutput == 1
    save([datadir,filename]);
else
end

