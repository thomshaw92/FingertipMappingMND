

%% ADDED REMINDER 12/01/24
input(sprintf('CHECK VOLUME IS 100'));


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

dets.psychvis = 0; % USE = 0; 1 = visual display on; 0 = off; STAYING OFF FOR SCANNER OUTER ROOM COMP DUE TO WEIRD LAGS
dets.tactorson = 1; % USE = 1; 0 = tactors not on; 1 = on
dets.keylock = 0; % USE = 0; lock the keyboard while experiment is on so you can't type anything other than specified keys
dets.figs = 1; % USE = 1; 1 = pop figures on screen for performance at the end; 0 = dont
dets.saveoutput = 1; % USE = 1; 0 = dont save; 1 = do save
dets.shuffle_trials = 1; % USE = 1; 1 = shuffle; 0 = don't
dets.fit_type = 1; % 1 = logit reg; 2 = (don't use) Weibull
dets.output_by_fing = 1; % 1 = split output for each finger tested; 0 = collapses over fingers tested
dets.pulsetype = 2; % 1 = sine wave; 2 = spaced pulse


% Set threshold level to use for curve fitting (proportion) - currently set for Weibull fitting only
thresh.value = .75;


%% Experimenter input section

% participant details
% subinit = 'HDJ'; % Manually enter for piloting
subinit = input('Participant initials: ', 's');
subinit = upper(subinit);

% subnum = 1;
subnum = input('Participant number: ');
if subnum < 10
     subcode = ['sub-00' num2str(subnum), '_', subinit];
else
     subcode = ['sub-0' num2str(subnum), '_', subinit];
end
clear subnum subinit

% Which hand?
% hand = 2; % 1 = left; 2 = right
hand = input('Which hand are you testing? Left = 1, right = 2: ');

% Experimental or practice
% maintrialsQ = 1; % 1 = experimental (main) trials; 0 = practice
maintrialsQ = input('Experimental or practice trials? Experimental = 1, practice = 0: ');

% Which session?
sessNum = input('What number session is this? e.g., 1/2: ');

% Patient or control
PatientOrControl = input('Patient = 1, or Control = 0?: ');


%% Script determines extra participant settings

% Set up how many fingers being tested
num_fings = 5; % testing 5 fingers

% Get hand name
if hand == 1
    hand_name_short = 'LEFT';
    hand_instruct = 'your LEFT hand';
elseif hand == 2
    hand_name_short = 'RIGHT';      
    hand_instruct = 'your RIGHT hand';
else
end

% Get patient or control name
if PatientOrControl == 1
    PatientOrControl = 'Patients';
elseif PatientOrControl == 0
    PatientOrControl = 'Controls';
else
end

% Date tag
clockdata = clock;
clockdata = clockdata(1:5);
datetag = sprintf('%d_%d_%d_%d_%d',clockdata); 
clear clockdata

% Build filename
filename = [datetag, '-', subcode, '-', 'VibroTest_sess', num2str(sessNum)];
% clear hand_name_short

% Add practice to filename (if relevant)
if maintrialsQ == 0
    filename = [filename, '_practice'];
else
end

% Set number of channels - WONT EVER CHANGE
num_chans = 6;

% If training - turn off output by finger (collapsing over fingers for training purposes)
if maintrialsQ == 0
    dets.output_by_fing = 0;
else
end


%% Pop filename on screen so experimenter can check participant dets and cancel out if details are wrong

input(sprintf('Check participant dets: %s - exit if incorrect', filename));
clear ans


%% Make dir for that participant in Data dir if it doesn't exist already

% PC
datadir = [pwd, '\Data\', PatientOrControl, '\', subcode,'\sess', num2str(sessNum), '\'];
% Mac % datadir = [pwd, '/Data/', PatientOrControl, '/', subcode,'/sess', num2str(sessNum), '/'];

if ~exist(datadir, 'dir')
    mkdir(datadir);
end


%% Make sounds

% General sound settings
amp = 1;
Fs = 48000;
dur = .25; % in seconds
time = (1 : dur * Fs);
phase = 0; % phase shift - we aren't using this so set to 0
freq = 30; % base frequency - flutter range

% % Get difficulty levels all and dif levels - if first test
levels(1,1) = 5; % test - must be even; using small number of difficulties (e.g., 4) but considering standard first as different trials to comparison first, so you end up with double the levels (e.g., 8) - this allows scoring 0-1 and use of logistic regression curves for fitting
levels(2,1) = 1; % Practice - must also be even. This is not an even number, but adds one on below to make 2 - so is even. 

% Get perc increments
for p_i = 1:2

    % Use no. of levels (above) to calc full range of levels to be tested
    perc_increments{p_i,:} = linspace(0.5,10, levels(p_i,1));
    % changed to make harder from this on 010722 (lowest value now 0.5 not 1) % perc_increments{p_i,:} = linspace(1,10, levels(p_i,1));

end
clear p_i levels

% Add another really easy level if practice
perc_increments{2,:} = [perc_increments{2,:} perc_increments{2,1}+10];
perc_increments{2,:} = flip(perc_increments{2,:},2); % reverse so very easy one is first

% Add increments to base frequency
for in = 1:2
    % get the right values
    perc_increments_i = perc_increments{in,:};

    % Add base freq onto them
    dif_levels_all{in,:} = freq+perc_increments_i; % Will make more s shaped later - fit to a cumulative gaussian

    clear perc_increments_i
end
clear in perc_increments


% Extract dif levels for this version of the experiment
if maintrialsQ == 1
    dif_levels = dif_levels_all{1,:};
else
    dif_levels = dif_levels_all{2,:};
end

% Make sounds
make_sound_070623


%% Set up trial/block details

% Repetition settings
% NOTE: NONE OF THE BELOW CREATE PROPER PARAMETRIC DESIGN WITH MORE THAN 1 FINGER (NUM_FING>1 I.E. IN TESTING) UNLESS FINAL N OF TRIALS = 16 OR MORE
if maintrialsQ == 1
    % Testing
    trials = 6; % Was 10*2 = 20 of each difficulty (10 either direection - first/ second faster) * 5 dif levels = 100 trials/ finger * 4 fings = 400 trials for test
    trials = trials * 2; % double the number of trials (so we have half one direction (comparison first) and half the other way)

    trials = trials * size(dif_levels,2); % per finger
    trials = trials * num_fings; % total trials
    
    % Blocks
    blocks = 4; % we might want more so they get more breaks
else
    % Practice trials
    trials = 1;
    trials = trials * num_fings;
    
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
trial_mat = zeros(trials, 9)+999;

% Generate base difficulty types from dif levels
if maintrialsQ == 1
    % Experimental trials
    types_dif = repmat(dif_levels, 1, trials/size(dif_levels,2) )';
else
    % Practice
    types_dif = [repmat(dif_levels, 1, trials )'];
    % types_dif = Shuffle(types_dif);
    types_dif = types_dif(1:trials, 1);
    types_dif = flip(sort(types_dif));
    % types_dif(1:2,:) = dif_levels(1);
    % types_dif(end,:) = dif_levels(end);
end

% Get fing types (and hand types for some conditions where hand is always the same)
types_fing = repmat(1:(num_fings), 1, (trials/num_fings) )';

% Sort finger types
types_fing = sort(types_fing,1);

% Add in which is faster 1st (1) or 2nd (2) - this allows you to make sure it's evenly distributed between the two for TESTING, which the randomise was not doing; Means we have exactly half first for all combinations of dif_levels/fing_types
% Not important for practice
if maintrialsQ == 1
    types_faster = [];
    for tf = 1:trials/2/size(dif_levels,2)
        types_faster_add = repmat(1:2, 1, size(dif_levels,2) )';
        types_faster_add = sort(types_faster_add,1);
        types_faster = [types_faster; types_faster_add];
        clear types_faster_add
    end
    clear tf
else
    types_faster = repmat(1:2, 1, trials)';
    % types_faster = Shuffle(types_faster);
    types_faster = types_faster(1:trials, 1);
end


% Randomise things for trial mat
if dets.shuffle_trials == 1
    % Get random numbers to randomise order
    order = 1:size(types_dif,1);
    order = order(randperm(length(order)));

    types_faster = types_faster(order);
    types_fing = types_fing(order);

    % if maintrialsQ == 1
        % NOT USING % Shuffle types dif (does not get shuffled in practice as we want the easy trials first)
        types_dif = types_dif(order);
    % else
    % end    
else
end
clear order


% Extra stuff for practice
if maintrialsQ == 0
    real_trial = 3;
else
end


% Add to trial_mat
row_dif = 3; row_fing = 4; row_faster = 5; 
trial_mat(:,row_dif) = types_dif;
trial_mat(:,row_fing) = types_fing;
trial_mat(:,row_faster) = types_faster;
clear types_dif types_faster types_fing
    

%% Initialise psychtoolbox

% % Audio

% Make sure any old audio stuff is closed
PsychPortAudio('Close');

if dets.tactorson == 1
    InitializePsychSound(1); %inidializes sound driver...the 1 pushes for low latency

    % Initialise two sound buffers for the two sounds
    pahandle = PsychPortAudio('Open', [], [], 2, Fs, num_chans, 0); % for the first played sound
    
    % % play test sound - load into buffer then play then wait
    testwait = size(testall,2) / Fs; % should be 1 sec
    PsychPortAudio('FillBuffer', pahandle, testall); PsychPortAudio('Start', pahandle, 1, 0); WaitSecs(testwait);
    clear testall testwait ans
else
end


% % Keyboard
% improve portability of your code across operating systems 
KbName('UnifyKeyNames');

% Disabling keyboard input to Matlab
if dets.keylock == 1
    ListenChar(2);
else
end
clear ans

% Reallow if needed - leave commented out ALWAYS
% ListenChar(1);


% % Visual
if dets.psychvis == 1
    % Had to add this to avoid warnings/ not running due to visual timing
    % error
    Screen('Preference', 'SkipSyncTests', 1);
    
    % Initialise some set up parameters
    PsychDefaultSetup(2);

    %Choosing the display
    screens=Screen('Screens'); screenNumber=max(screens); clear screens

    %Open Screen
    % [window, windowRect] = PsychImaging('OpenWindow', screenNumber, 255/2); % do not use PsychImaging call, does not work most of the time, use the below
    % [window, windowRect]=Screen('OpenWindow', screenNumber,[128 128 128]); % From Ash
    [window, windowRect]=Screen('OpenWindow', screenNumber,[], [10 20 600 300]); % small debugging window

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


%% General instructions

if dets.psychvis == 1
    if maintrialsQ == 0
        for il = 1:2
            
            % General instructions settings
            Screen('TextSize', window, 40);
        
            if il == 1
                % First instruction - put hands/ fingers on tactors
                DrawFormattedText(window, sprintf('Please place the fingers of %s on the tactors, \n and two fingers of your other hand on the ''1'' and ''2'' keys to respond. \n \n Press any key when you are ready to continue', hand_instruct), 'center', 'center', [0 0 0]);
                Screen('Flip', window);
            else
                % Second instruction - task
                DrawFormattedText(window, sprintf('On each trial, you will feel two pulses. One will be faster and one slower. \n Your task is to identify which pulse was faster. \n \n Press the ''1'' key if the first pulse was faster\n and the ''2'' key if the faster one was second. \n \n You can take your time, but try to be as accurate as you can. \n If you are unsure, take your best guess.\n \n When you are ready, press any key to begin the experiment...'), 'center', 'center', [0 0 0]);
                Screen('Flip', window);
            end
        end
        
    else
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
    WaitSecs(2);

else
end

    % Pause
    WaitSecs(2);


%% Trial loop

% Clear command window
home

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

    % Put up instructions if training (certain trials)
    if maintrialsQ == 0 && c == real_trial
        % Get message
        realmsg = 'Real training trials beginning';

        if dets.psychvis == 1
            % Let participants know their real trials are starting (no feedback)
            Screen('TextSize', window, 40);
            DrawFormattedText(window, sprintf(realmsg), 'center', 'center', [0 0 0]);
            Screen('Flip', window);
        else
            sprintf('Real training trials beginning')
        end

        WaitSecs(3);
        
        if dets.psychvis == 1
            % Redraw black fixation
            Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 0], [xCentre yCentre], 2);
            Screen('Flip', window);
        else
        end
    else
    end

    % Get difficulty level & pair for this trial
    c = c+1;
    curr_diff = trial_mat(c,row_dif);
    curr_fing = trial_mat(c,row_fing);
    curr_faster = trial_mat(c,row_faster);


    %% Get sounds - for the right finger(s)

    % Get appropriate matrix of sounds for this finger (all frequencies)
    sound_trial = eval(sprintf('x%d', curr_fing));
    clear curr_fing

    % Get the standard frequency sound for this finger
    sound_standard = sound_trial{1,:};

    % Work out which position the comparison sound is in (add one as base stim (30) is 1
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
        else
            sprintf('Training trial (with answer): Which was faster?\n\n answer = %s', order_message)
        end
        
        % Pause
        WaitSecs(2);
    else
    end

    clear order_message


    %% Play sound - not in a loop, to reduce processing time between sounds for accuracy

    if dets.tactorson == 1
        
        % Load into buffer
        PsychPortAudio('FillBuffer', pahandle, playsound1);

        % Play sound 1
        PsychPortAudio('Start', pahandle, 1, 0);

        % Pause length of sound (dur) so it completes, then pause twice that time again for an actual gap between sounds
        WaitSecs(dur + (dur*2));

        % Load second sound into buffer
        PsychPortAudio('FillBuffer', pahandle, playsound2);

        % Play sound 2
        PsychPortAudio('Start', pahandle, 1, 0);

        % Pause so sound completes
        WaitSecs(dur);
        
    else
    end
    
    % Start time counter for RT
    % t1 = GetSecs; tic

    clear playsound1 playsound2


    %% Get response

    % Initialise resp to blank
    resp = [];

    % Set question
    question = ('Which was faster? First sound (press ''1'') or second sound (press ''2''): ');

    if dets.psychvis == 0
        resp = input(question, 's');
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
    elseif resp == '2'
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
    if maintrialsQ == 0
        % Test - practice
        trial_feed = 1;
    else
        trial_feed = 0;
    end
    
    % Display trial feedback
    if trial_feed == 1
        if dets.psychvis == 0
            input([feedback ' - press any key to continue'], 's');
        else
            Screen('TextSize', window, 40);
            DrawFormattedText(window, sprintf(feedback), 'center', 'center', feedcol);
            Screen('Flip', window);
        end
    else
    end
    
    % Clear command window
    home

    clear ans feedcol feedback trial_feed
    clear curr_diff curr_tactor curr_faster


    %% Add to trial matrix & save
    row_resp = 8; row_cor = 9;
    trial_mat(c,1) = block;
    trial_mat(c,2) = trial;
   % PASTED FROM ABOVE: row_dif = 3; row_fing = 4; row_tactor = 5
    trial_mat(c,6) = sound_order(1);
    trial_mat(c,7) = sound_order(2);
    trial_mat(c,row_resp) = resp;
    trial_mat(c,row_cor) = cor;
    
    % Add to counters for this block
    counter_cor = [counter_cor cor];
    counter_trials = counter_trials + 1;

    clear cor resp sound_order

%     % Save
%     if dets.saveoutput == 1
%         save([datadir,filename]);
%     else
%     end

    % Pause between trials
    WaitSecs(1);


%% Pause at end of blocks

    if maintrialsQ == 1
        if ismember(trial, trial_breaks)
            
            % Calculate perc corr
            perc_cor_block = [perc_cor_block, ( sum(counter_cor)/sum(counter_trials) )*100];
            
            
            % Present end of block feedback
            if trial == trials
                feedback_end = sprintf('End of experiment. Great job! \n\n Your last block score = %d percent \n Your best score so far = %d percent \n\n Press any key to exit', round(perc_cor_block(end),0), round(max(perc_cor_block),0) );
            else
                feedback_end = sprintf('End of block %d (from %d). Great job! \n\n Your last block score = %d percent \n Your best score so far = %d percent \n\n Press any key when you are ready to go on', block, blocks, round(perc_cor_block(end),0), round(max(perc_cor_block),0) );
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

                clear keyIsDown timedout_b

            end
            clear feedback_end
            
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
    
    % Save
    if dets.saveoutput == 1
        save([datadir,filename]);
    else
    end
    
    
% end trial loop
end

clear block trial
clear x1 x2 x3 x4 x5
clear pahandle1 pahandle2
clear ans
clear counter_cor counter_trials

% Undo psychtoolbox stuff - where applicable
if dets.keylock == 1
    % Re-enable keypresses to matlab
    ListenChar(0);
else
end

% Clear the screen visuals if relevant
if dets.psychvis == 1
    sca
else
end


clear keylock psychtool trainQ screenNumber lineWidthPix window windowRect xCentre yCentre allCoords
clear ans
clear pahandle

% Save
if dets.saveoutput == 1
    save([datadir,filename]);
else
end


% Get experimental duration
experimental_duration = toc/60;


%% AT END - Score data

if c == trials
    
    % Re add for debugging: row_dif = 3; row_fing = 4; row_faster = 5; row_resp = 8; row_cor = 9; datadir = [pwd, '/'];
    % For some inital subs also: sessNum = 1; filename = [filename, '_sess', num2str(sessNum)]; thresh = rmfield(thresh, 'coords');
     
    % Determine how many times we need to do scoring/ plotting - depending on whether output is bring split by finger or not
    % Re add for debugging % dets.output_by_fing = 1;
    if dets.output_by_fing == 1
        scoreplot_reps = num_fings+1;
    else
        scoreplot_reps = 1;
    end

    % Score data
    score_prop_data_030723
    
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
            if maintrialsQ == 1 
                % Plot "prop faster" - use in testing
                figure(sr2)
                scatter(dif_mat(rowd.ratio,:), dif_mat(rowd.faster_prop,:), 'r*'); % logged ratio of difference between standard and comparison
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
                scatter(dif_mat(rowd.ratio,:), dif_mat(rowd.corr_prop,:), 'b*'); % logged ratio of difference between standard and comparison
                % scatter(1:size(dif_mat,2), dif_mat(6,:), 'r*'); % artificially using 1-8 as x-axis
                ylabel('Proportion correct')
                xlabel('Ratio of standard & comparison stimulus (log)')
                ylim([0 1])
                grid on
                set(gca,'fontsize',14)
            end

            % % Get accuracy message & add to plot
            % Get loc to put message
            loc = dif_mat(3,end);
   
            % Get acc
            %  old - only gets acc for all trials - acc_plot = mean(perc_cor_block);
            if maintrialsQ == 1
                if sr2 < scoreplot_reps
                    corrs = trial_mat(trial_mat(:,row_fing) == sr2, row_cor);
                else
                    corrs = trial_mat(:, row_cor);
                end
            else
                corrs = trial_mat(:, row_cor);
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
        if maintrialsQ == 1

            % % Get vars needed - calling them the same as in orig scripts for continuity
            dataStims = dif_mat(rowd.ratio,:);
            % dataProp - below - differs by fit type
            dataResp = dif_mat(rowd.faster_num,:); % Num faster (used by logit reg)
            dataCount = dif_mat(rowd.trials_num,:);

            % Create extended version of dataStims (more values) so can fit a smooth curve
            dataStims_long = linspace(dataStims(1), dataStims(end), 1000);

            % Initialise empty var for params (then if not filled we know of curve fitting issue)
            params = [];

            % Set curve fit error to 0 - changes below if needed
            curve_fit_error(sr2,1) = 0;

            % % Fit function
            if dets.fit_type == 1
                dataProp = dif_mat(rowd.faster_prop,:); % Prop faster
                
                % % Fit logistic regression
                fit_logit_reg
                fit_name = 'logit reg';
                
            elseif dets.fit_type == 2
                dataProp = dif_mat(rowd.corr_prop,:); % Prop corr - don't use (used by Weibull)
                
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
            
        % end if maintrialsQ is 1 loop (for fitting)   
        else
        end
       
        
        % Save image
        if dets.saveoutput == 1
            
            % Generate name to save figure
            if maintrialsQ == 1
                titlef = sprintf([num2str(filename), ' ', fit_name, ' fit']);
                % titlef = sprintf([num2str(datetag), ' - ', subcode, ' - Test - ', fit_name, ' fit']);
            elseif maintrialsQ == 0
                titlef = sprintf([num2str(filename)]);
                % titlef = sprintf([num2str(datetag), ' - ', subcode, ' - Practice test']);
            else
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
    clear row_fing row_dif row_faster row_cor row_resp row_hand row_tactor
    
% end of is trials finished loop
end


%% Final save
if dets.saveoutput == 1
    save([datadir,filename]);
else
end

