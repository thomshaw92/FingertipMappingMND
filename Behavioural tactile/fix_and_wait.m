

% Change to fixation
Screen('DrawLines', window, allCoords, lineWidthPix, [0 0 0], [xCentre yCentre], 2);
Screen('Flip', window);

% Pause
WaitSecs(1);