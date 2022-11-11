
% Get details for single pulse

% % Very short square wave pulse (up only) of set size
pulse_size = 100;
pulse = ones(1,pulse_size)*amp; % No good as for faster freqs you need to make the pulse shorter to fit all the pulses in you need to be at the right frequency
% pulse = [zeros(1,pulse_size), ones(1,100)*amp, zeros(1,100)]; % this one had zeros either side for padding, but you are adding that yourself with the ISI so dont need it, also it means your pulse is long meaning you fit less pulses in, interfering with Hz rate
clear pulse_size

% % [NOT USING] Wave version - not using as has negative numbers, want to avoid for new stims
% freq_sp = freq_loop;
% dur_sp = (1/freq_sp)/2;
% time_sp = (1 : dur_sp * Fs);
% clear dur_sp
% pulse = amp*sin(2*pi*(freq_sp/Fs)*time_sp+phase); % sine wave
% pulse = amp*square(2*pi*(freq_sp/Fs)*time_sp+phase); % square wave
% clear time_sp freq_sp

% % [NOT USING] Short square wave pulse (up only) of varying size
% dur_sp = (1/freq_loop)/2;
% time_sp = (1 : dur_sp * Fs);
% clear dur_sp
% pulse = [0, ones(1,size(time_sp,2))*amp, 0];

% Visualise to check
% plot(pulse); ylim([-.1 10.1])



% Make empty vector to fill pulses into
x = [];

% Convert ISI from Hz to sec
isi = 1/freq_loop;
% isi = 1/freq_loop/2; % if using short square wave pulse of varying size

% Get pause length in vector units
isi_vector = zeros(1, size((1 : isi * Fs),2) );
clear isi

% Loop to add stimulation and ISI while xo is under the size of time vector
while size(x,2) < size(time,2)
    
    % Add a pulse
    x = [x, pulse];
    
    % Add a gap - thought I needed to start with a gap to avoid start
    % click, but also seems ok - check all stimuli. Putting gap at start
    % means you get less stimuli in so its not ideal. Also seems to
    % successfully make the first tap even though no gap in front, so all good
    x = [x, isi_vector];
        
end
clear isi_vector pulse

% Clip to exactly right length
x = x(1:size(time,2));

% Add 20,000 vector units (correct for Fs 48k) to 0 to prevent final clicks
% - may not be needed, check all stimuli, as putting gap in at the end is
% also not ideal as you lose more stimuli
% x(1, end-20000:end) = 0;

% Visualise
% figure(5); plot(x); ylim([-.1 10.1])


%% Test play on tactor 1

% % Create sound on channel 1 only
% testplay = [x; zeros(1,size(x,2)); zeros(1,size(x,2)); zeros(1,size(x,2)); zeros(1,size(x,2)); zeros(1,size(x,2))];
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
% WaitSecs((size(x,2)/Fs)+1);
