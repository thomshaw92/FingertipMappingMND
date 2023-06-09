% Set up Psychtoolbox
Screen('Preference', 'SkipSyncTests', 1); % Skip sync tests for faster performance
%Choosing the display
screens=Screen('Screens'); screenNumber=max(screens); clear screens
backgroundCol = [128 128 128];
[window, windowRect]=Screen('OpenWindow', screenNumber,backgroundCol, [200 600 1100 1300]); % small debugging window

% Define parameters
dotSize = 80; % Size of the dot in pixels
TR = 1; % TR in seconds (time between flickers)
flickerRate = 1 / TR; % Calculate flicker rate in Hz
screenRect = Screen('Rect', window); % Get the screen rectangle
screenHeight = screenRect(4); % Height of the screen in pixels
lowerHalfRect = [0 screenHeight/2 screenRect(3) screenHeight]; % Define the rectangle for the lower half of the screen

dotColor1 = [34 139 34]; % Color of the dot in RGB format
dotColor2 = [128 128 128]; % Color of the dot in RGB format

% Set up timing
t0 = GetSecs(); % Get the initial time
maxDuration = 10; % Max duration of flickering in seconds

% Start flickering
while true
    % Check if time limit has been reached
    currentTime = GetSecs();
    if currentTime - t0 > maxDuration
        break; % Exit the loop if time limit has been reached
    end

    % Alternate between dot colors
    if mod(round((currentTime - t0) * flickerRate), 2) == 0
        dotColor = dotColor1; % Color 1 (green)
    else
        dotColor = dotColor2; % Color 2 (grey)
    end
    
    % Draw the dot
    DrawFormattedText(window,'Please move your body part', 'center', 'center', [0 0 0]);
    Screen('FillOval', window, dotColor, CenterRect([0 0 dotSize dotSize], lowerHalfRect));
    Screen('Flip', window);
    
    % Wait for the next flicker
    WaitSecs(1 / flickerRate);
end

% Clean up
sca; % Close the window