
% Get details for single pulse

% % Very short square wave pulse
pulse_size = 100;
pulse = ones(1,pulse_size)*amp;
% pulse = [zeros(1,100), ones(1,pulse_size)*amp, zeros(1,100)]; % with zeros either side for padding - no good as once you get to high freqs the padding mean you can't fit the right number of pulses in to hit your Hz rate
clear pulse_size

% % [NOT USING] Sine wave version
% freq_sp = 150;
% dur_sp = (1/freq_sp)/2;
% time_sp = (1 : dur_sp * Fs);
% clear dur_sp
% pulse = amp*sin(2*pi*(freq_sp/Fs)*time_sp+phase); % sine wave
% pulse = amp*square(2*pi*(freq_sp/Fs)*time_sp+phase); % square wave
% clear time_sp freq_sp

% Visualise to check
% plot(pulse); ylim([-.1 10.1])



% Make empty vector to fill pulses into
x = [];

% Convert ISI from Hz to sec
isi = 1/freq_loop;

% Get pause length in vector units
isi_vector = zeros(1, size((1 : isi * Fs),2) );
clear isi

% Loop to add stimulation and ISI while 'x' is under the size of time vector
while size(x,2) < size(time,2)
    
    % Add a pulse
    x = [x, pulse];
    
    % Add a gap - thought I needed to start with a gap to avoid start
    % click, but also seems ok - check all stimuli. Putting gap at start
    % means you get less stimuli in so its not ideal
    x = [x, isi_vector];
        
end
clear isi_vector pulse

% Clip to exactly right length
x = x(1:size(time,2));

% Add 20,000 vector units (correct for Fs 48k) to 0 to prevent final clicks
% - may not be needed, check all stimuli, as putting gap in at the end is
% also not ideal as you lose more stimuli
% xo(1, end-20000:end) = 0;

% Visualise
% figure(5); plot(x); ylim([-.1 10.1])


%% Test play on tactor 1

% % Create sound on channel 1 only
% testplay = [xo; zeros(1,size(xo,2)); zeros(1,size(xo,2)); zeros(1,size(xo,2)); zeros(1,size(xo,2)); zeros(1,size(xo,2))];
% 
% % Closes audio device
% PsychPortAudio('Close');
% 
% % % Audio
% InitializePsychSound(1); %inidializes sound driver...the 1 pushes for low latency
% 
% % Initialise sound buffer
% pahandle = PsychPortAudio('Open', [], [], 2, Fs, num_chans, 0);
% 
% % Fill test sound into buffer
% PsychPortAudio('FillBuffer', pahandle, testplay);
% 
% % Play test sound
% PsychPortAudio('Start', pahandle, 1, 0);
% 
% WaitSecs((size(xo,2)/Fs)+1);
