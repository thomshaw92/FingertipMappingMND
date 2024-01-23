

%% Make short test sound

% Get duration & freq for test sound
dur_test = .1;
freq_loop = 20;

% Get time based on duration
time_test = (1 : dur_test * Fs);

% Make test sound
test = amp*sin(2*pi*(freq_loop/Fs)*time_test+phase); % sine wave
clear dur_test freq_loop time_test

% Put on all channels
if num_chans == 6
    testall = [test; test; test; test; test; test];
else
end
clear test


%% Make experimental sounds

% Set up counter
cl = 0;

% l = 1;
for l = 1:size(dif_levels,2)+1
    
    % Get freq for this loop
    if l == 1
        freq_loop = freq;
    else
        freq_loop = dif_levels(cl);
    end
    
    % Make sound base part
    if dets.pulsetype == 1
        % Sine wave
        x = amp*sin(2*pi*(freq_loop/Fs)*time+phase);
    elseif dets.pulsetype == 2
        % Spaced pulse
        make_spaced_pulse_070723
    end
    
    % Add to counter
    cl = cl+1;
    
    % Make zeros of same size as base sound
    zs = zeros(1, size(x,2));
    
    % NEEDS TO BE CHECKED ON NEW TACTORS SO ORDER IS CORRECT X1 PLAYS ON FINGER 1 ETC
    x1{cl,:} = [x; zs; zs; zs; zs; zs];
    x2{cl,:} = [zs; x; zs; zs; zs; zs];
    x3{cl,:} = [zs; zs; x; zs; zs; zs];
    x4{cl,:} = [zs; zs; zs; x; zs; zs];
    x5{cl,:} = [zs; zs; zs; zs; x; zs];

    clear zs x
    clear freq_loop

end

clear amp phase l cl time st


%% Sound testing stuff - also do not use

% % Make sure any old audio stuff is closed
% PsychPortAudio('Close');
% 
% InitializePsychSound(1); %inidializes sound driver...the 1 pushes for low latency
% 
% % Initialise two sound buffers for the two sounds
% pahandle = PsychPortAudio('Open', [], [], 2, Fs, num_chans, 0); % for the first played sound
% 
% % Put into buffer
% PsychPortAudio('FillBuffer', pahandle, xsound);
% 
% % Play test sound
% PsychPortAudio('Start', pahandle, 1, 0);
% WaitSecs(dur+1);
% 
% end

