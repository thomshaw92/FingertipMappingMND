
% Set chans - never changes
num_chans = 6;

% Set num tactors
num_tactors = 5;

% Enter between?
enter = 1;

% Pre-set order (weird numbering needed to get tactors to play 1-5)
order = 0;

% Get order for number of tactors
if num_tactors == 5
    % % This order is different from the ones below as I moved the plugs in the front of the soundcard so now we get sound in left to right order plugging chans1/2 in to port 2.1, chans 3/4 into centre/bass, chans 5/6 into port 5.1)
    order_tacs = [1, 2, 3, 5, 6, 4]; % channel 4 does nothing (on testplay 6)
    
    % order_tacs = [1, 2, 5, 3, 4, 6];
    % order_tacs = [1, 2, 5, 3, 4, 6];
    % order_tacs = [1, 2, 5, 6, 3, 4];
else
end

% General sound settings
amp = 5;
Fs = 48000;
dur = 1; % in seconds
time = (1 : dur * Fs);
phase = 0;
% phase = 4.8; % phase shift - we aren't using this so set to 0
freq = 10;

% Make sound base part
% x = zeros(1, size(time,2));
% x = ones(1, size(time,2));
% x = [zeros(1, size(time,2)/2), ones(1,100), zeros(1,size(time,2)/2)];
% x = amp*square(2*pi*(freq/Fs)*time+phase); % square wave
x = amp*sin(2*pi*(freq/Fs)*time+phase); % sine wave
% x = x+amp;
% x = [zeros(1,100000), x, zeros(1,100000)];
% x = [x, zeros(1,20000)];
x(x <= 0) = 0;
% x(1,end-20000:end) = 0; % 20000 IS THE MAGIC NUMBER
% x = x(1,1:92000);

% figure(1); plot(x); % refline(0)

% Make zeros - no sound
x_zeros = zeros(1,size(x,2));


% Load test sound onto the right number of channels
if num_chans == 6
    testplay0 = [x_zeros; x_zeros; x_zeros; x_zeros; x_zeros; x_zeros];
    testplay1 = [x; x_zeros; x_zeros; x_zeros; x_zeros; x_zeros];
    testplay2 = [x_zeros; x; x_zeros; x_zeros; x_zeros; x_zeros];
    testplay3 = [x_zeros; x_zeros; x; x_zeros; x_zeros; x_zeros];
    testplay4 = [x_zeros; x_zeros; x_zeros; x; x_zeros; x_zeros];
    testplay5 = [x_zeros; x_zeros; x_zeros; x_zeros; x; x_zeros];
    testplay6 = [x_zeros; x_zeros; x_zeros; x_zeros; x_zeros; x];
else
end


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
% pause(5)
% l = 1;
for l = 1:6


    if order == 1
        if l == 1
            ll = order_tacs(1);
        elseif l == 2
            ll = order_tacs(2);
        elseif l == 3
            ll = order_tacs(3);
        elseif l == 4
            ll = order_tacs(4);
        elseif l == 5
            ll = order_tacs(5);
        else
            ll = order_tacs(6);
        end
        
        testplay_loop = eval(sprintf('testplay%d',ll));
        clear ll

    else
        testplay_loop = eval(sprintf('testplay%d',l));
    end


    
    if enter == 1
        input(sprintf('testplay%d',l));
    else
    end

    % Fill test sound into buffer
    PsychPortAudio('FillBuffer', pahandle, testplay_loop);
    clear testplay_loop

    % Play test sound
    PsychPortAudio('Start', pahandle, 1, 0);


    % Wait
    % WaitSecs(dur);
    WaitSecs(size(x,2)/Fs);
% pause(1)
end
% clear testplay stim ans



% PsychPortAudio('Close', pahandle);
PsychPortAudio('Close');



%% Psychtoolbox test stuff

% version = PsychPortAudio('Version');
% count = PsychPortAudio('GetOpenDeviceCount');
% devices = PsychPortAudio('GetDevices');

clearvars
