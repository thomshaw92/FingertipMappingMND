

timedout_test = false;

while ~timedout_test
    [ keyIsDown, ~, keyCode ] = KbCheck;
    if(keyIsDown), break; end
end

KbName(keyCode)