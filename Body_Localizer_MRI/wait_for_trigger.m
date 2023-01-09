
    
% Set timeout boolean
if run_num == 0
    % does not wait for trigger
    timedout_tr = true;
else
    % DOES wait for trigger
    timedout_tr = false;
end

% Wait for trigger
while ~timedout_tr

    % Check for scanner trigger
    [ ~, ~, keyCode ] = KbCheck;

    % if(keyIsDown), break; end
    if( strcmp(KbName(keyCode), '5%') ), timedout_tr = true; end
end

% If triggered - start timer
if timedout_tr == true
    
    % Start timer
    t0 = GetSecs;

    % Start back up timer
    tic
end
    
clear keyCode timedout_tr

