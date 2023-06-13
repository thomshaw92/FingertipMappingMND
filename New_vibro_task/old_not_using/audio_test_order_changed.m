
%% get participant number and associated tactor order

% get participant number
subnum = input('Participant Number: ');

% Load orders
load('C:\Users\uqhdemp1\Desktop\Hons_testing_2022_HDJ\tac_combos.mat');
clear tac_combos

% Get order for that participant based on their participant number
tac_order = tac_order_mat(subnum, 3:6);
clear tac_order_mat subnum

% Pop tactor order on screen to be checked
input(sprintf('place tactors in the order (from left to right): %d %d %d %d - press enter once this is done', tac_order));


%% Sound dets

% Set chans
num_chans = 6;

% Enter between?
enter = 1;

% General sound settings
amp = 1;
Fs = 48000;
dur = .25; % in seconds
time = (1 : dur * Fs);
phase = 0; % phase shift - we aren't using this so set to 0
freq = 30; %

 % Make sound base part
x = amp*sin(2*pi*(freq/Fs)*time+phase); % sine wave

% Make zeros - no sound
zs = zeros(1,size(x,2));


%% Rearrange

% note these names are for Jack's order 1,2,3,4 left hand, but will work on Ying's too 1,2 L hand 3,4 R hand
space_order_names = ["LL", "LCL", "LCR", "LR"]; % Numbering the fingers by where they sit spatially
% space_order = [1, 2, 3, 4]; % these are the finger numbers that associate with the space orders in the var above

LL = [x; zs; zs; zs; zs; zs]; % left hand mat - left-most tactor
LCL = [zs; x; zs; zs; zs; zs]; % left hand mat - centre left tactor
LCR = [zs; zs; zs; zs; x; zs]; % left hand mat - centre right tactor
LR = [zs; zs; zs; zs; zs; x]; % left hand mat - right-most tactor

% Rearrange spatial positions to match tactor order
space_order_names_ordered_by_tactor = space_order_names(tac_order);

% loop to mix spatial order and tactor order
% st = 1;
for st = 1:4

    % Select the spatial position for that tactor order
    xsound = eval(space_order_names( (tac_order(st)) ));
    % space_order_names( (tac_order(st)) )

    if st == 1
        % Make x1 sound
        x1 = xsound;
    elseif st == 2
        x2 = xsound;
    elseif st == 3
        x3 = xsound;
    elseif st == 4
        x4 = xsound;
    else
    end

end

clear zs x
clear amp phase st time
clear LCR LR RL RCL



%% Play sounds

% Closes audio device
% PsychPortAudio('Close', pahandle);
PsychPortAudio('Close');

% % Audio
InitializePsychSound(1); %inidializes sound driver...the 1 pushes for low latency

% Initialise sound buffer
pahandle = PsychPortAudio('Open', [], [], 2, Fs, num_chans, 0);


% Fill test sound into buffer
% PsychPortAudio('FillBuffer', pahandle, testplay0);

% Play test sound - can fix issues with timing later
% PsychPortAudio('Start', pahandle, 1, 0);

% l=1;
for l = 1:4

    testplay_loop = eval(sprintf('x%d',l));

    if enter == 1
        input(sprintf('testplay%d',l));
    else
    end

    % Fill test sound into buffer
    PsychPortAudio('FillBuffer', pahandle, testplay_loop);
    clear testplay_loop

    % Play test sound - can fix issues with timing later
    PsychPortAudio('Start', pahandle, 1, 0);

    WaitSecs(dur);

end
% clear testplay stim ans


% % Psychtoolbox test stuff
% version = PsychPortAudio('Version');
% count = PsychPortAudio('GetOpenDeviceCount');
% devices = PsychPortAudio('GetDevices');

clearvars
