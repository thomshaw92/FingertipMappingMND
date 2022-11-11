

%% Make short test sound

% Get duration & freq for test sound
dur_loop = .1;
freq_loop = 10;

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

    % Get time based on duration
    time = (1 : dur_freq * Fs);

    % Make zeros of size = time
    z = zeros(1, size(time,2));

    % Make sound of size = time
    if pulsetype == 1
        x = amp*sin(2*pi*(freq_loop/Fs)*time+phase); % sine wave
        
        % Remove negative values - if relevant
        if pulsetype_removeneg == 2
            x(x<0) = 0;
        else
        end
        
    elseif pulsetype == 2
        make_spaced_pulse_140922
    else
    end

    % Count pulses & plot for first 1 second
    pulses = numel(findpeaks(x(1, 1:Fs)));
    % figure(fl); plot(x);
    if pulsetype == 2
        % Add one as does not count first pulse which comes at the very start with no gap, so does not see it as a peak
        pulses = pulses+1;
%         xlim([-1000 size(x,2)]);
%         ylim([-1 8]);
    else
    end
    freqs_actual(1, fl) = pulses;
    clear pulses

    
    %% Make sound - correct for whichever order we input

    % Make sound that plays on all channels and tactors
    if num_chans == 6
        tacall = [x; x; x; x; x; x];
    end
    
    
    %% Loop to make sound for single fingers/ tactors
    
    % Loop to make sound for each finger - use tactor order
    % tl = 1;
    for tl = 1:num_chans
    
        % Get name for the desired tactor
        namefing = sprintf('t%d', tl);

        % Get number for the desired tactor - using order
        whichfing = tacorder(tl);
        
        % Check this isn't one of the channels we aren't using (taczeros)
        if ~ismember(whichfing, taczeros)

            % % If NOT a channel that is turned off
            % Create generic sound with same thing on all channels (all long)
            tacfing = tacall;

            % Work out which fingers should be turned to 0 = tactor/ channels not being used (taczeros) as well as all other fingers aside from the finger chosen for this loop
            turnoff = tacorder;
            turnoff = turnoff(turnoff~=whichfing); % Remove all fingers other than the finger for this loop

            % Loop to change those channels to 0
            for tz = 1:size(turnoff,2)
                tacfing(turnoff(tz),:) = z;
            end
            clear tz turnoff
            
        else
            % If it IS a channel we are turning off
            tacfing = zeros(num_chans, size(time,2) );
        end

%             % For debugging only - Plot figures to sense check
%             figure(1); plot(time,tacfing(1,:)); ylim([-.1 amp+.1]);
%             figure(2); plot(time,tacfing(2,:)); ylim([-.1 amp+.1]);
%             figure(3); plot(time,tacfing(3,:)); ylim([-.1 amp+.1]);
%             figure(4); plot(time,tacfing(4,:)); ylim([-.1 amp+.1]);
%             figure(5); plot(time,tacfing(5,:)); ylim([-.1 amp+.1]);
%             figure(6); plot(time,tacfing(6,:)); ylim([-.1 amp+.1]);
%             WaitSecs(1);

            % Put that sound into a structure
            tac.(namefing) = tacfing;

%             % For debugging only - Testplay
%             PsychPortAudio('FillBuffer', pahandle, tac.(namefing)); PsychPortAudio('Start', pahandle, 1, 0); WaitSecs(dur_loop+2);

            clear tacfing namefing whichfing

    % end tl loop
    end
    clear tl
    
    
    

    %% Store with freq & finger label

    % Get name
    stim_name = sprintf('tac_f%d', freq_loop);

    % Put in struct
    stims.(stim_name) = tac;

    clear stim_name
    clear tacall tac x z
    clear freq_loop
    clear time

% end freq loop
end
clear fl

clear amp phase time

