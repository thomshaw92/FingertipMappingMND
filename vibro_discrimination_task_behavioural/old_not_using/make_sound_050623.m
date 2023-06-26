

% Set up counter
cl = 0;

% l = 1;
for l = 1:size(dif_levels,2)+1
    
    if l == 1
        freq_loop = freq;
    else
        freq_loop = dif_levels(cl);
    end
    
    % Make sound base part
    x = amp*sin(2*pi*(freq_loop/Fs)*time+phase); % sine wave
    
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


    % Set up sounds based on position in space - ONLY SET UP FOR 2 HANDS, I/M, 6 CHANNELS
    space_order_names = ["LCR", "LR", "RL", "RCL"]; % Numbering the fingers by where they sit spatially
    % space_order = [1, 2, 3, 4]; % these are the finger numbers that associate with the space orders in the var above

    LR = [zs; x; zs; zs; zs; zs]; % left hand mat - right most tactor
    LCR = [x; zs; zs; zs; zs; zs]; % left hand mat - centre right tactor
    RL = [zs; zs; zs; zs; x; zs]; % right hand mat - left most tactor
    RCL = [zs; zs; zs; zs; zs; x]; % right hand mat - centre left tactor

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
            x1{cl,1} = xsound;
        elseif st == 2
            x2{cl,1} = xsound;
        elseif st == 3
            x3{cl,1} = xsound;
        elseif st == 4
            x4{cl,1} = xsound;
        else
        end

    end

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

