
% Copied largely identically from score_prop_data script in learning layers dir on 240522 (with some things removed)

% For debugging
% row_diff = 3; row_orient = 4; row_resp = 5; row_cor = 6; row_count_cor = 7; row_count_trial = 8; row_perc_cor = 9; row_revs = 10; row_top_reps = 11; row_dir = 12;

%% Create difficulty matrix for scoring

% Record order of dif_levels used in new var
dif_levels_used = dif_levels;

% Unshuffle (if relevant) dif_levels
dif_levels = sort(dif_levels,2);

% Add levels to matrix
dif_mat = [flip(dif_levels) dif_levels]; % dif levels
dif_mat(2,:) = [ones(1,size(dif_levels,2)) ones(1,size(dif_levels,2))+1]; % down/ across

% Work out how many times to loop
ds_loops = size(dif_levels,2) * 2;

% Add empty values to matrix to be filled
dif_mat(3,:) = 999; % number of trials; set iteratively below
dif_mat(4,:) = 999; % num correct
dif_mat(5,:) = 999; % proportion corr
dif_mat(6,:) = 999; % num comparison faster
dif_mat(7,:) = 999; % prop comparison faster

% Add artificial 8 to -8 code to allow plotting (no good as it adds a 0 in the middle when plotting)
dif_mat(8,:) = [flip(dif_levels) -dif_levels];
% dif_mat(8,:) = [-flip(dif_levels) dif_levels];

% Add data labels
dif_labels = {'8 across', '6 across', '4 across', '2 across', '2 down', '4 down', '6 down', '8 down'};
% dif_labels = {'8 across', '6 across', '4 across', '2 across', ' ', '2 down', '4 down', '6 down', '8 down'};
% dif_labels = {'8 down', '6 down', '4 down', '2 down', ' ', '2 across', '4 across', '6 across', '8 across'};


%% Loop to extract data

% ds = 1;
for ds = 1:ds_loops

    % Get current difficulty
    dif_score = dif_mat(1,ds);

    % Get current orientation down/across
    downacc_order = dif_mat(2,ds);

    % Index of this combo of difficulty and orientation in dif_mat
    i1 = find(dif_mat(1,:)==dif_score);
    i2 = find(dif_mat(2,:)==downacc_order);
    [i,~]=intersect(i1,i2);
    clear i1 i2

    % Start counter for this difficulty
    cs = 0;

    % Initialise blank matrix for diff data
    data = [];

    % ts = 1;
    for ts = 1:size(trial_mat,1)
        
        % Initiate add to 0
        add = 0;

        % Does the duration of this trial match the duration being counted for this loop?
        if round(trial_mat(ts,row_diff),2) == round(dif_score,2)
            add = 1;
        else
            add = 0;
        end

        % Is the orientation (down/acc) match the orientation ''?
        if trial_mat(ts, row_orient) == downacc_order
            % Leave as above
        else
            add = 0;
        end

        % If conditions are right to add - add
        if add == 1
            
            % Add to counter
            cs = cs + 1;

            % Add corr data
            data(cs,1) = trial_mat(ts,row_cor); % corr/not in 1/0 format

            % Get prop "presentation was down" data
            prop_down = trial_mat(ts,row_resp);

            % Recode so is 1/0 not 1/2
            if prop_down == 2
                prop_down = 0;
            else
            end

            % Add into matrix for summing below
            data(cs,2) = prop_down;
            clear prop_down
        else
        end

        clear add

    end

    % Add to dif_mat
    dif_mat(3,i) = cs;
    dif_mat(4,i) = sum(data(:,1)); % no. correct
    dif_mat(5,i) = dif_mat(4,i)/dif_mat(3,i); % prop corr
    dif_mat(6,i) = sum(data(:,2)); % no. first faster
    dif_mat(7,i) = dif_mat(6,i)/dif_mat(3,i); % prop faster

    clear ts cs dif_score downacc_order i data

% end ds loop
end

clear ds_loops ds

