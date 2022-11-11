

% Timeout boolean
timedout = false;

while ~timedout
    % Check if a key is pressed
    [ keyIsDown, ~, keyCode ] = KbCheck; % if you want to include RT you need keyTime: [ keyIsDown, keyTime, keyCode ] = KbCheck; 
    if(keyIsDown), break; end
    % RT = keyTime - t1; actual_RT_approx = toc-dur;
    % if( RT > resp_limit ), timedout = true; end % if you want a time limit on your waiting for response period
end

% Store key pressed
if(~timedout)
    resp = KbName(keyCode);
end

clear keyIsDown keyCode timedout
clear ans