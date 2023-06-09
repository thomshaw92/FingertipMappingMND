

%% Make short test sound

% Get duration & freq for test sound
dur_loop = .1;
freq_loop = 20;

% Get time based on duration
time = (1 : dur_loop * Fs);

% Make test sound
test = amp*sin(2*pi*(freq_loop/Fs)*time+phase); % sine wave
clear dur_loop freq_loop time

% Put on all channels
if num_chans == 6
    testall = [test; test; test; test; test; test];
else
end
clear test


%% Make main sounds

% Loop for frequency
% fl = 1;
for fl = 1:size(freqs,2)
    
% Get freq for this loop
freq_loop = freqs(fl);

    % Loop for duration
    % dl = 1;
    for dl = 1:size(durs,2)

    % Get full duration
    dur_loop = durs(dl);

    % Get time based on duration
    time = (1 : dur_loop * Fs);
    
    % Make zeros of same size as ODDBALL (for stims that will be off)
    z = zeros(1, size(time,2));

    % Make sound for ODDBALL (goes for full duration)
    if pulsetype == 1
        xo = amp*sin(2*pi*(freq_loop/Fs)*time+phase); % sine wave
    elseif pulsetype == 2
        make_spaced_pulse_310822
    else
    end

    % Count pulses and check Hz - for debugging (note, misses the first peak as it is at 0, thus is an underestimate), added 1 for this reason
    if pulsetype == 1
        freq_actual(1,fl) = numel(findpeaks(xo(1,1:Fs)));
    else
        freq_actual(1,fl) = numel(findpeaks(xo(1,1:Fs)))+1;
    end
    
    % [not using, makes 30 way too hard] Get dif dur = 1 cycle
    % difdur = 1/freq_loop;

    % Get length of ODDBALL in vector units
    odd = difdur * Fs;

    % Make sound for non-oddballs (length of oddballs in vector units set to 0 - no sound)
    x = xo;
    x(1, end-odd:end) = 0;
    clear odd
    % figure(7); plot(xo); hold on; plot(x); hold off
    

    %% Make sound where all tactors are on and are length of oddball (longer)

    % Make sound for right number of channels and tactors
    if num_chans == 6
        tacall = [x; x; x; x; x; x];
    end

    % Turn tactors that should be zero to zero
    tacall(taczeros,:) = z;

    % Loop to make sound for oddball of each tactor - use tactor order
    % ol = 1;
    for ol = 1:num_chans

            % Get name for the desired tactor
            nameodd = sprintf('t%d', ol);

            % Get number for the desired tactor - using order
            whichodd = tacorder(ol);

            % % If tactor is NOT supposed to be zero - create an oddball template
            if ~ismember(whichodd, taczeros)

                % Create generic sound with same thing on all channels (all long)
                tacodd = tacall;

                % Change correct channel to oddball
                tacodd(whichodd,:) = xo;

%                 % Plot figures to sense check
%                 figure(1); plot(time,tacodd(1,:)); ylim([-.1 amp+.1]);
%                 figure(2); plot(time,tacodd(2,:)); ylim([-.1 amp+.1]);
%                 figure(3); plot(time,tacodd(3,:)); ylim([-.1 amp+.1]);
%                 figure(4); plot(time,tacodd(4,:)); ylim([-.1 amp+.1]);
%                 figure(5); plot(time,tacodd(5,:)); ylim([-.1 amp+.1]);
%                 figure(6); plot(time,tacodd(6,:)); ylim([-.1 amp+.1]);
%                 WaitSecs(2);

                % Put that sound into a structure
                tac.(nameodd) = tacodd;
                
                % Testplay
                % PsychPortAudio('FillBuffer', pahandle, tac.(nameodd)); PsychPortAudio('Start', pahandle, 1, 0); WaitSecs(dur_loop+2);


            % end is member (playing sound)    
            else
            end
            
            clear tacodd nameodd whichodd

        % end ol loop
    end
    clear ol


    %% Store with freq and dur labels

    % Turn dur to char
    dur_loop_char = num2str(dur_loop);
    
    % Split into before and after
    dur_loop_char1 = extractBefore(dur_loop_char, '.');
    dur_loop_char2 = extractAfter(dur_loop_char, '.');
    clear dur_loop_char

    % Get name
    stim_name = sprintf('tac_f%d_d%sp%s', freq_loop, dur_loop_char1, dur_loop_char2);

    % Add freq and dur info to struct
    tac.freq = freq_loop;
    tac.dur = dur_loop;
    tac.dur1 = dur_loop_char1;
    tac.dur2 = dur_loop_char2;
    clear dur_loop_char1 dur_loop_char2
    
    % Put in struct
    stims.(stim_name) = tac;

    clear tac stim_name
    clear dur_loop_char dur_loop
    clear tacall x xo z

    % end dur loop
    end
    clear dl
    clear freq_loop

% end freq loop
end
clear fl

clear amp phase time

