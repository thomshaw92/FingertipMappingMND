

for t = 1:wait_for
    
    % Set timeout boolean
    if run_num == 0
        % does not wait for trigger
        timedout_tr = true;
    else
        % DOES wait for trigger
        timedout_tr = false;
    end

    while ~timedout_tr

        % Check for scanner trigger
        [ ~, ~, keyCode ] = KbCheck;

        % if(keyIsDown), break; end
        if( strcmp(KbName(keyCode), '5%') ), timedout_tr = true; end
    end

    if timedout_tr == true
        
        % Reset timer
        timedout_tr = false;
        
        if ctr == 0
            % Start timer
            t0 = GetSecs;
            
            % Start back up timer
            tic
            
        else
        end
        
        % Flash message (if move trial)
        if ismember(event_type, subcond_block)
        else
        end
        
    end
    
    % Wait for half a TR - reenable in plenty of time to get next triggr
    WaitSecs(TR/2);
    
    % Add to tr counter
    ctr = ctr + 1;

    clear keyCode timedout_tr

end
clear t

% Add seconds to timings matrix
timings(1,ctr) = GetSecs - t0;

% Add event type to timings matrix
timings(2,ctr) = event_type;

% Add predicted timing (based on TR) to timings matrix
timings(3,ctr) = ctr*TR;

clear wait_for event_type

toc


