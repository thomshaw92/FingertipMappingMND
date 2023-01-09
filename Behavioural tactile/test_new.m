% Ask for participant details
p_name = input('Participant initials: ', 's');
p_age = input('Participant age: ');
hand = input('Which hand? Left = 1, Right = 2: ');
fing = input('Which finger? 1 = thumb; 2 = index; 3 = middle; 4 = ring; 5 = little: ');

% Initialize variables
strengths = [];

% Test grip strength for each finger
for i = 1:5
    if i == fing
        fprintf('Testing grip strength for %s finger\n', fing{i});
    else
        fprintf('Testing grip strength for %s finger\n', fing{i});
    end
    
    % Measure grip strength
    strength = measure_grip_strength();
    
    % Record strength
    strengths(i) = strength;
end

% Test grip strength for whole hand
fprintf('Testing grip strength for whole hand\n');
strength = measure_grip_strength();
strengths(6) = strength;

% Get current working directory
cwd = pwd;

% Build file path
fname = sprintf('%s/%s_%d_%d_%d.txt', cwd, p_name, p_age, hand, fing);

% Open file for writing
fid = fopen(fname, 'w');

% Write results to file
fprintf(fid, 'Participant: %s\nAge: %d\nHand: %d\nFinger: %d\n', p_name, p_age, hand, fing);
fprintf(fid, 'Finger strengths:\n');
for i = 1:5
    fprintf(fid, '%s: %d\n', fing{i}, strengths(i));
end
fprintf(fid, 'Hand strength: %d\n', strengths(6));

% Close file
fclose(fid);
