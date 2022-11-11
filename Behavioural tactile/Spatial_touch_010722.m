
% % Note from Zhang 2019 JOV Usually, one block of 3- down/1-up staircase with a 10% step size produces about a dozen reversals in 80 trials. The estimated threshold of the block is calculated by averaging stimulus levels at even numbers of reversals after deleting the first four or five of them.
% - Work out what to do for scoring for staircase - might need to read a bit (see above)
%  Knowing the differential threshold (how much between thresholds found) can be used to set the step size optimally
% Ideal = 50% drops until 3rd reversal, then 10% -- estimated around 20-25 trials prodes a reliable thresh under various conditions


%% Clean up
close all;
clearvars;

% turn off sci notation
format short g


%% Start timer for experiment duration
tic


%% General details

% Settings
dets.psychvis = 1;
dets.keylock = 0;
dets.figs = 1; % 1 = pop figures on screen for performance at the end; 0 = dont
dets.saveoutput = 1; % 0 = dont save
dets.shuffle_trials = 1; % 1 = shuffle; 0 = don't
dets.pinsorgratings = 2; % 1 = pins device; 2 = gratings

% Threshold
thresh.value = .75;

% Text size for psychtoolbox visuals
text_size_ptb_instructions = 30;
text_size_ptb_other = 40;


%% Enter details

% participant details
% p_init = 'XXX'; % Manually enter for piloting
p_init = input('Participant Intitials: ', 's');
% subnum = 1;
subnum = input('SUBJECT Number: ');
if subnum < 10
     subcode = ['P00' num2str(subnum)];
else
     subcode = ['P0' num2str(subnum)];
end
sub = [subcode, ' ', p_init];

% Age
% p_age = '35';
p_age = input('Participant Age: ', 's');

% Which finger
% fing = 3; % 1 = thumb; 2 = index; 3 = middle; 4 = ring; 5 = little
fing = input('Which finger? 1 = thumb; 2 = index; 3 = middle; 4 = ring; 5 = little: ');

% Which hand - for Jack testing always LEFT
% hand = 1; % 1 = left; 2 = right
hand = input('Which hand? Left = 1, Right = 2: ');

% Handedness
handedness_LRA = input('Handedness? Left-handed = 1; right-handed = 2; ambidextrous = 3: ');

% Proper trials?
% maintrialsQ = 1; % 1 = experimental (main) trials; 0 = practice
maintrialsQ = input('Experimental or practice trials? Experimental = 1, practice = 0: ');

% Type of test - always 1 = MOCs for honours testing
% testType = 1; % 1 = MOCs; 2 = staircase
testType = input('Type of test? 1 = MOCs; 2 = Staircase: ');


%% Computer gets details from above settings

% Get test type name
if testType == 1
    test_use = 'MOCs';
else
    test_use = 'staircase';
end

% Get fing name
if fing == 1
    fing_name = 'thumb';
elseif fing == 2
    fing_name = 'index';
elseif fing == 3
    fing_name = 'middle';
elseif fing == 4
    fing_name = 'ring';
else
    fing_name = 'little';
end

% Get hand name
if hand == 1
    hand_name = 'LEFT';
else
    hand_name = 'RIGHT';
end


%% Build and show filename

% Date tag
clockdata = clock;
clockdata = clockdata(1:5);
datetag = sprintf('%d_%d_%d_%d_%d',clockdata); 
clear clockdata

% Build filename
filename = [datetag, '_', subcode, '_', p_init, '-', 'Spatial_touch_', test_use, '_', hand_name, '_', fing_name];
clear p_init subcode subnum p_age test_use

% Add practice to filename (if relevant)
if maintrialsQ == 0
    filename = [filename, '_practice'];
else
end

% Flash file name up to check
input(sprintf('check filename: %s - exit if incorrect', filename));


%% Initialise psychtoolbox

% % Keyboard
% improve portability of your code across operating systems 
KbName('UnifyKeyNames');

% Disabling keyboard input to Matlab
ListenChar(2);
% ListenChar(1);    
    
if dets.psychvis == 1
    % % Visual
    % Initialise some set up parameters
    PsychDefaultSetup(2);

    %Choosing the display
    screens=Screen('Screens'); screenNumber=max(screens); clear screens

    %Open Screen
    [window, windowRect] = PsychImaging('OpenWindow', screenNumber, 255/2);
    % [window, windowRect]=Screen('OpenWindow', screenNumber,[], [10 20 600 300]); % little debugging window

    % Set screen parameters
    Screen('TextSize', window, text_size_ptb_instructions);

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

% % If practice put instructions up
% if maintrialsQ == 0
% 
%     % instr_loop = 1;
%     for instr_loop = 1:3
%         
%         if dets.psychvis == 1
%             % Screen('TextSize', window, text_size_ptb);
%         else
%         end
%     
%         if instr_loop == 1
%             % First part of message 1
%             message1 = 'Today we will be presenting stimulation to your %s %s finger. \n Please turn your %s hand so the palm is facing up and resting on the foam support. \n \n ';
%     
%             % How to continue - varys by test
%             if testType == 1
%                 % MOCs
%                 message1b = 'Place your other hand on the response buttons. \n \n ';
%                 message1c = 'Press one of the response buttons when you are ready to continue...';
%                 message = [message1, message1b, message1c];
%                 clear message1 message1b
%             else
%                 % Staircase
%                 message1c = 'Press the spacebar when you are ready to continue...';
%                 message = [message1, message1c];
%                 clear message1
%             end
%     
%             % Add vars
%             present = sprintf(message, hand_name, fing_name, hand_name);
%             clear message
%             
%         elseif instr_loop == 2
%             % Instructions - task
%             message2 = 'On each trial, you will feel the testing device touch your %s %s finger. \n \n There are two prongs on the testing device. \n These prongs will be either aligned DOWN the length of your finger, \n or ACROSS it (the experimenter will demonstrate these positions now). \n \n Your task is to identify whether the prongs were oriented DOWN or ACROSS. \n \n';
%             message = [message2, message1c];
%             clear message2
%             
%             % Add vars
%             present = sprintf(message, hand_name, fing_name);
%             clear message
%             
%         elseif instr_loop == 3
%             % Response
%             if testType == 1
%                 message3 = 'Press the button marked "D" if the prongs were oriented down your finger and "A" if they were oriented across. \n \n Try to be as accurate as you can. \n If you are unsure, take your best guess.\n \n';
%             else
%                 message3 = 'Say "down" alound if the prongs were oriented down your finger and "across" if they were oriented across. \n \n Try to be as accurate as you can. \n If you are unsure, take your best guess.\n \n When you are ready, press the spacebar to continue...';
%             end
%     
%             message = [message3, message1c];
%             clear message3
%     
%             present = sprintf(message);
%             clear message message1c
%     
%         else
%             present = sprintf('The experimenter will now help you put on an eye mask (so you cannot see) /n and headphones playing white noise (so you cannot hear). \n \n Please let the experimenter know if this will be an issue for you. \n \n Then once you are ready we will begin the experiment...');
%         end
%         
%         if dets.psychvis == 1
%             % Present visuals in window
%             DrawFormattedText(window, present, 'center', 'center', [0 0 0]);
%             Screen('Flip', window);
%             
%             % Wait for key to continue
%             wait_for_key
%             clear resp
%         else
%             % Present text in command window
%             input(present, 's');
%         end
%         clear present
%         
%         % Fixation and 1 sec wait
%         fix_and_wait
%     
%     % end instr_loop    
%     end
%     
%     clear ans instr_loop
%     
%     % Fixation and 1 sec wait
%     fix_and_wait
% 
% % end of if practice    
% else
% end


%% Set up trials

% Get difficulty levels - different for pins and gratings
if dets.pinsorgratings == 1
    % % Pins
    % get number of levels
    if testType == 1
        levels = 4; % This doubles to 8 (4 levels down, 4 across) for psychophysics reasons
    else
        levels = 7; % Gets all levels from 2-8
    end
    
    % get dif levels
    dif_levels = linspace(2,8, levels); % Make more S shaped for fitting purposes
    clear levels

elseif dets.pinsorgratings == 2
    % % Gratings
    if testType == 1
        dif_levels = [0.5, 1, 2, 3];
    else
        dif_levels = [0.5, 1, 1.5, 2, 3, 4, 5, 6];
    end
else
end


% Set trials for each diff level - will be changed with piloting
if testType == 1
    % MOCs
    trials = 10; % must be even, change to 12 ish later
else
    % Staircase
    trials = 3; % doing 3 aligned with typical 3 down 1 up proc
end

% Change back to smaller number of trials/ difs if practice
if maintrialsQ == 0
    dif_levels = dif_levels(end);
    trials = 2; % must be even
else
end

% Increase number of trials if MOCs
if testType == 1
    % Double the trials - so we count forward/ reverse trials as separate
    trials = trials * 2;
    
    % Increase trials by number of diff levels
    trials = trials * size(dif_levels,2);
else
    if maintrialsQ == 0
        trials = trials * 2;
    else
    end
end


%% Set up blocks

% Set number of blocks
if maintrialsQ == 1 && testType == 1
    blocks = 4; % Change to 4 later probs
else
    blocks = 1;
end

% Work out where breaks will be if multiple blocks
trial_breaks = [];

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

% Initialise block to 1 - gets changed later
block = 1;


%% While loop
% keep runnning until condition is met - repeats for staircase, just does 1 for MOCS

% Initialise trial counter
c = 0;

% Initialise counter to track loops of while
counter_while = 0;

% Set direction indicator to 0 (not up or down)
dir_updown = 0;

% Set reversals to 0 - while loop ending depends on this var
counter_reversals = 0;

% Set counter for repeats (when you get the same diff wrong) - while loop ending can also depend on this var
counter_top_repeats = 0;

% Initialise while condition boolean to false
finish_while = false;

% Initialise holder for all block perc cors
perc_cor_diff = [];


while finish_while == false

%% Generate trial types

    % Get list of trial types
    if testType == 1
        % % MOCs

        % Shuffle diffs (if relevant)
        if dets.shuffle_trials == 1
            dif_levels = dif_levels(randperm(length(dif_levels)));
        else
        end

        % Initialise empty matrix for trial_types data
        types_diff = [];

        % Generate trial types
        for tt = 1:size(dif_levels,2)
            types_diff = [types_diff; repmat(dif_levels(tt), 1, trials/size(dif_levels,2) )'];
        end
        clear tt

    else
        % % Staircase
        if counter_while == 0
            % Make vector of easiest difficulty
            types_diff = repmat(dif_levels(length(dif_levels)), 1, trials)';
        else
            % Make vector of new (changed) difficulty - change based on performance
            types_diff = repmat(change_diff, 1, trials)';
            clear change_diff
        end
    end


    %% Generate list of orientation types

    % Initialise empty mat for data
    types_orient = [];

    % Work out how many cycles to do based on test type
    if testType == 1
        run_for = size(dif_levels,2);
    else
        run_for = 1;
    end

    % Loop to generate orientations
    for ot = 1:run_for
        % Generate matrix of 1's and 2's the length of our trials
        if testType == 1
            ot_dat = repmat(1:2, 1, trials/2/size(dif_levels,2) );
        else
            ot_dat = randi(2,1, trials); % use for 3 down 1 up method, will not have even number of downs and acrosses
            % ot_dat = 1:2; ot_dat = ot_dat(randperm(length(ot_dat))); ot_dat = [ot_dat, randi(2,1,1)]; ot_dat = ot_dat(randperm(length(ot_dat))); % did this way to not get three of 1 orientation
            % ot_dat = repmat(1:2, 1, trials/2 ); % when doing even number of trials and parametrically getting same number of downs and acrosses, not possible with 3 down 1 up method
        end

        % Sort it
        ot_dat = sort(ot_dat,2);

        % Shuffle it
        if dets.shuffle_trials == 1
            ot_dat = ot_dat(randperm(length(ot_dat)));
        else
        end

        % Add this to the main matrix
        types_orient = [types_orient; ot_dat'];
        clear ot_dat
    end
    clear ot run_for


    %% Make trial mat and add details

    % Number of cols needed for trial mat
    if testType == 1
        num_cols = 9;
    else
        num_cols = 12;
    end

    % Where to add details
    row_diff = 3; row_orient = 4;

    % Set up/ append mat and add data
    if testType == 1 || (testType == 2 && counter_while == 0)

        % Set up new trial matrix to record performance
        trial_mat = zeros(trials, num_cols)+999;

        % Add trial types
        trial_mat(:, row_diff) = types_diff;
        trial_mat(:, row_orient) = types_orient;

    elseif (testType == 2 && counter_while >= 1)

        % Append new trial mat rows onto old one
        trial_mat = [trial_mat; zeros(trials, num_cols)+999];

        % Add trial types
        trial_mat(c+1:c+trials, row_diff) = types_diff;
        trial_mat(c+1:c+trials, row_orient) = types_orient;

    else
    end

    clear num_cols
    clear types_diff types_orient


    %% Trial loop

    % Initialise var to allow while loop to run
    finish_trials = false;

    % Set text size
    if dets.psychvis == 1
        Screen('TextSize', window, text_size_ptb_other);
    else
    end

    while finish_trials == false
    % trial = 1;
    % for trial = 1:loop_length
    
        % Add to trial counter
        c = c+1;

        % Get difficulty for this trial
        curr_diff = trial_mat(c,row_diff);

        % Get orientation for this trial
        curr_or = trial_mat(c,row_orient);


        %% Present difficulty info on screen where appropriate

        % Set default present info to 0 (don't present dif info)
        present_diff = 0;

        % Work out if this is a trial to present difficulty info
        if c == 1
            % If first trial
            present_diff = 1;
        else
            % Not first trial - but change in dif_level between this trial and last
            if trial_mat(c,row_diff) ~= trial_mat(c-1,row_diff)
                present_diff = 1;
            else
            end
            
            % Not first trial - but last one was wrong so we skipped some trials
            if ~isempty(perc_cor_diff) && perc_cor_diff(end) == 0 && trial_mat(c-1,row_resp) == 999
                present_diff = 1;
            else
            end
        end

        % Present difficulty info - if the right trial (determined above)
        if present_diff == 1

            % If not trial 1 (no data yet) - Add contents of counters to mat as perc (just for MOCS as staircase does this at the end)
            if testType == 1 && c ~= 1
                perc_cor_diff = [perc_cor_diff, (sum(counter_cor)/sum(counter_trial)) ];
            else
            end

            % Start/re-start counters
            counter_cor = [];
            counter_trial = [];

            % Make trial diff message
            message_dif = sprintf('Difficulty level %.2f - Press any key to continue', curr_diff);

            if dets.psychvis == 1
                % Screen('TextSize', window, text_size_ptb);
                DrawFormattedText(window, message_dif, 'center', 'center', [0 0 1]);
                Screen('Flip', window);

                % Wait for key to continue
                wait_for_key
                clear resp

            else
                input(message_dif, 's');
            end

            % Fixation and 1 sec wait
            fix_and_wait

        else
        end

        clear ans message_dif present_diff


        %% Present orientation info on screen - EVERY trial

        % Initialise resp to blank
        resp = [];

        % Get orientation in words
        if curr_or == 1
            curr_or_words = 'DOWN';
        else
            curr_or_words = 'ACROSS';
        end

        % Make orientation message
        message_orient = sprintf('Present %s \n (size %.2f) \n\n then submit response, d = down, a = across \n and press Enter to continue: ', curr_or_words, curr_diff);

        if dets.psychvis == 1
            % Screen('TextSize', window, text_size_ptb);
            DrawFormattedText(window, message_orient, 'center', 'center', [0 0 0]);
            Screen('Flip', window);

            % Wait for response + enter
            wait_for_key

        else
            resp = input(message_orient, 's');
            clear ans
        end

        clear message_orient curr_or_words 
        
        % Clear curr_diff only if MOCS
        if testType == 1
            clear curr_diff
        else
        end

        % Fixation and 1 sec wait - removed in place of correct/ incorrect added below
        % fix_and_wait


        %% Recode response

        % Edit cell responses - just take first value of cell and make it not a cell
        if iscell(resp)
            resp = resp{1};
            resp = num2str(resp);
        else
        end

        % Change resp to 0 if participant pressed something weird
        if isempty(resp) || iscell(resp) || size(resp,2) ~= 1
            resp = 0;
        else
        end

        % Turn into numbers - if an expected response d/a
        if resp == 'd'
            resp = 1;
        elseif resp == 'a'
            resp = 2;
        else
            resp = 0;
        end


        %% Score & present outcome on screen

        % Check if correct & display feedback ( 1 = left; 2 = right)
        if curr_or == 1 && resp == 1
            cor = 1;
        elseif curr_or == 2 && resp == 2
            cor = 1;
        else
            cor = 0;
        end

        clear curr_or

        % Add to counters for trials of the same dif_level
        counter_cor = [counter_cor, cor];
        counter_trial = [counter_trial, 1];

        % Present correct or incorrect on screen
        if dets.psychvis == 1
            % Screen('TextSize', window, text_size_ptb);
            if cor == 1
                DrawFormattedText(window, sprintf('Correct'), 'center', 'center', [0 1 0]);
            else
                DrawFormattedText(window, sprintf('Incorrect'), 'center', 'center', [1 0 0]);
            end
            Screen('Flip', window);
        else
            if cor == 1
                input(sprintf('Correct'), 's');
            else
                input(sprintf('Incorrect'), 's');
            end
            clear ans
        end
        
        % Wait
        WaitSecs(1);
        

        %% Add to trial matrix & save
        row_resp = 5; row_cor = 6; row_count_cor = 7; row_count_trial = 8; row_perc_cor = 9; row_revs = 10; row_top_reps = 11;

        trial_mat(c,1) = block;
        trial_mat(c,2) = c;
        % diff added above as col 3 (row_diff)
        % orient added above as col 4 (row_orient)
        trial_mat(c,row_resp) = resp;
        trial_mat(c,row_cor) = cor;
        trial_mat(c,row_count_cor) = sum(counter_cor);
        trial_mat(c,row_count_trial) = sum(counter_trial);
        trial_mat(c,row_perc_cor) = trial_mat(c,row_count_cor) / trial_mat(c,row_count_trial);
        
        if testType == 2
            trial_mat(c,row_revs) = counter_reversals;
            trial_mat(c,row_top_reps) = counter_top_repeats;
        else
        end

        clear ans resp

        % Save
        if dets.saveoutput == 1
            save([pwd, '/Data/',filename]);
        else
        end
        
        
        %% Cancel trial_loop or allow to continue
        
        if testType == 1
            % % If its MOCS
            % If number of trials is the max
            if c == trials
                
                % Change var to cancel loop
                finish_trials = true;
            else
            end
        else
                % % If its staircase
                % If got last answer wrong
                if cor == 0

                    % Change var to cancel loop
                    finish_trials = true;

                    % Change c to skip those missed trials
                    c = c + (trials - sum(counter_trial));

                % If you finished all 3 trials for that set
                elseif sum(counter_trial) == trials
                     % Change var to cancel loop
                    finish_trials = true;
                end
            
        end
        
        clear cor
        

        %% End block feedback

        % If its the right trial - break - MOCS only
        if testType == 1 && maintrialsQ == 1
            if ismember(c, trial_breaks)

                % Get feedback
                feedback_end = sprintf('End of block %d (from %d)\n\n Press Enter to continue', block, blocks);

                if dets.psychvis == 0
                   input(feedback_end, 's');
                else
                    % Screen('TextSize', window, text_size_ptb);
                    DrawFormattedText(window, sprintf(feedback_end), 'center', 'center', [0 0 0]);
                    Screen('Flip', window);

                    % Wait for key
                    wait_for_key
                    clear resp
                end

                clear feedback_end

                % Fixation and 1 sec wait
                fix_and_wait

                % Change block number
                block = block + 1;

            else
            end
        else
        end

    % end trial while/ for loop
    end
    
    clear finish_trials
    % clear loop_length

    % Get final perc_cor_block entry
    perc_cor_diff = [perc_cor_diff, (sum(counter_cor)/sum(counter_trial)) ];
    clear counter_cor counter_trial
    
    % If staircase - decide what to do next
    if testType == 2
        
        % Add to while counter
        counter_while = counter_while + 1;
        
        % Change difficulty (or not) based on performance - 3 down, 1 up
        if perc_cor_diff(end) == 1
            
            % % Got all 3 correct - make harder by 1
            % Indicate going harder
            dir_updown_change = -1;
            
            % Check its possible to make it harder
            if curr_diff ~= dif_levels(1)
                
                % If there is room to get harder
                change_diff = dif_levels(1, find(dif_levels==curr_diff)-1 ); % must have a vector of dif levels specified, can only change within this range
                % change_diff = curr_diff - 1; % allows changing level outside a set range
                
            else
                % If at hardest level already - just repeat bottom level
                change_diff = dif_levels(1);
                
                % Make a warning
                WARN{c} = 'tried to make diff harder but was at lowest level';
                
                % And artificially put a counter reversal in to move towards end of exp
                counter_reversals = counter_reversals + 1;
                
                % Reset counters - as normal stuff above wont work
                counter_cor = []; counter_trial = [];
            end
        else
            % % Wasn't all correct - make easier by 1
            % Indicate going easier
            dir_updown_change = 1;
            
            % Check it's possible to make easier
            if curr_diff ~= dif_levels(end)
            
                % If there is room to make it easier
                change_diff = dif_levels(1, find(dif_levels==curr_diff)+1 ); % must have a vector of dif levels specified
                % change_diff = curr_diff + 1;
                
            else
                % At easiest level already - just repeat top level
                change_diff = dif_levels(end);
                
                % Make a warning
                WARN{c} = 'tried to make diff easier but was at highest level';
                
                % And add to counter to move towards end of exp
                counter_top_repeats = counter_top_repeats + 1;
                
                % Reset counters - as normal stuff above wont work
                counter_cor = []; counter_trial = [];
            end
        end
        
        clear curr_diff
        
        % Work out whether there was a reversal (don't do this on first trial (when dir_updown == 0) as no reversal is possible yet as no previous trials
        if dir_updown ~= 0 && dir_updown ~= dir_updown_change
            % Reversal occured
            counter_reversals = counter_reversals + 1;
        else
        end
        
        % Add to trial mat
        if testType == 2
            row_dir = 12;
            trial_mat(c,row_dir) = dir_updown_change;
        else
        end
        
        % Reset dir_updown to changed value
        dir_updown = dir_updown_change;
        
        clear dir_updown_change

        % Reset boolean to stop while loop
        if counter_reversals == 7
            % Did 7 staircase reversals - ideal stop point
            finish_while = true;
        elseif counter_top_repeats == 7
            % Got the easiest one wrong 7 times (can't do task)
            finish_while = true;
        else
            % It's not time to finish while loop - Reset trial loop counter so will go do more loops
            finish_trials = false;
        end
        
    else
        % If MOCS
        finish_while = true;
    end

% end while loop
end

clear block
clear change_diff finish_trials finish_while dir_updown
    

% Exit and close psychtool stuff
if dets.psychvis == 1
    sca
    
    % Enabling keyboard input to Matlab
    ListenChar(0);
else
end

% Re-enable keyboard
if dets.keylock == 1
    % Reset the keyboard input checking for all keys (place out of loop)
    RestrictKeysForKbCheck;

    % Re-enable echo to the command line for key presses (CTRL+C to exit)
    ListenChar(1)
else
end

clear ans
clear allCoords lineWidthPix screenNumber window windowRect xCentre yCentre
clear text_size_ptb_instructions text_size_ptb_other

% Save
if dets.saveoutput == 1
    save([pwd, '/Data/',filename]);
else
end


%% End of MOCs scoring

% Display acc if test/ practice
if testType == 1 && c == trials && maintrialsQ == 0
    input(sprintf('perc cor diff: %s', num2str(perc_cor_diff)));
else
end

% Do scoring if test/ main trials
if testType == 1 && c == trials && maintrialsQ == 1
    
    %% Create matrix for difficulty level and score
    % for debugging: row_diff = 3; row_orient = 4; row_resp = 5; row_cor = 6; row_count_cor = 7; row_count_trial = 8; row_perc_cor = 9; row_revs = 10; row_top_reps = 11;

    score_prop_data
    

    %% Plot outcome
    if dets.figs == 1
        
        % Plot raw data
        figure(1)
        scatter(dif_mat(8,:), dif_mat(7,:), 'r*');
        % scatter(1:size(dif_mat,2), dif_mat(7,:), 'r*'); % x axis is 1:8 matrix (no good, as gives threshold in 1-8, which are not our stimuli)
        ylabel('Proportion "down"')
        xlabel('Condition')
        % xticklabels(combined_name_label) - does not work (doesn't align with data points but tick marks, so is not what we need AND needs to be reversed to plot anyway as positive ratios (e.g.40/30) go to the left automatically on matlab, where they need to be right for the way the labels are mapped out
        ylim([0 1])
        % grid on
        set(gca,'fontsize',12)
        
        % % This is for when using the two-point device
        % Edit xtick values
        % xticks([flip(dif_mat(8,:))])
        % xticklabels(dif_labels)
        % xtickangle(45)
        
        % Add mean acc data
        txt_tr = sprintf('Mean Acc = %.2f', mean(perc_cor_diff));
        text(dif_mat(8,4), .15, txt_tr,'FontSize',12, 'HorizontalAlignment', 'right')
        clear txt_tr
    else
    end
    
    %% Curve fitting, plotting etc.
    % Runs several sub-scripts
    
    curve_fit_parent

    
% end of trials are finished loop 
end

clear row_cor row_count_cor row_count_trial row_diff row_orient row_perc_cor row_resp row_dir row_revs row_top_reps


%% End of staircase

if testType == 2 && c == size(trial_mat,1)
    
    if dets.figs == 1
        
        % Plot raw data
        x = 1:size(trial_mat,1)';
        
        figure(1)
        li = plot(x, trial_mat(:,3));
        li.Color = [0 0 0];
        li.LineWidth = 1.5;
        ylim([dif_levels(1)-.5 dif_levels(end)+.5]);
        xlim([1 size(trial_mat,1)]);
        clear li
        
        hold on
        vals = zeros(size(trial_mat,1),1);
        for vl = 1:6
            val = find(trial_mat(:,10)==vl); val = val(1); vals(val,1) = trial_mat(val,3);
        end
        scatter(x, vals, 'r*')
        clear vals val vl x
        
        ylabel('Difficulty level')
        xlabel('Trial')
        
        grid on
        set(gca,'fontsize',14)
        
        if dets.saveoutput == 1
            
            % Generate name to save figure
            titlef = sprintf(['Participant ', sub, ' ', hand_name, ' hand ', fing_name, ' finger']);
            title(titlef);
            
            titlef = [num2str(datetag), ' ', titlef];
            
            % Add practice where relevant and .bmp
            if maintrialsQ == 0
                titlef = [titlef ' practice.bmp'];
            else
                titlef = [titlef '.bmp'];
            end

            % Save image
            saveas(gcf, [pwd, '/Data/', (titlef)]);
            clear titlef
    
        else
        end
        
    else
    end
    
    clear thresh
    
else
end

clear trial datetag sub

% Get experiment duration
experiment_duration = toc/60;

% Save
if dets.saveoutput == 1
    save([pwd, '/Data/',filename]);
else
end


