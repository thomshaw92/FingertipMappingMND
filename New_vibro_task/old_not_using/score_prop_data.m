

%% Create matrix for scoring
% As of 01/07/22, when splitting output by finger, you get a matrix for
% each finger but also a final one (sr = 5) collapsed over all fingers

for sr = 1:scoreplot_reps
    
    % Work out what to add at top of matrix - dif for test and train
    if testtrainQ == 1
        if maintrialsQ == 1
            dif_mat = [flip(dif_levels) dif_levels]; % dif levels
        else
            dif_mat = [dif_levels flip(dif_levels)]; % dif levels
        end
        dif_mat(2,:) = [ones(1,size(dif_levels,2)) ones(1,size(dif_levels,2))+1]; % which faster
        ds_loops = size(dif_levels,2) * 2; % loop twice the size of dif levels - as we have trials where first faster/ second faster are considered different
    else
        dif_mat = dif_levels; % dif levels
        dif_mat(2,:) = ones(1, size(dif_mat,1)); % which faster (always 1, not considering first/ second faster as different trials)
        ds_loops = size(dif_levels,2); % just loop once through dif levels (not twice, as not considering first/ second faster as '')
    end

    % Add same stuff to bottom of all
    dif_mat(3,:) = 999; % ratio of comparison to standard
    dif_mat(4,:) = 999; % number of trials; set iteratively below
    dif_mat(5,:) = 999; % num correct
    dif_mat(6,:) = 999; % proportion corr
    dif_mat(7,:) = 999; % num comparison faster
    dif_mat(8,:) = 999; % prop comparison faster


    %% Make labels for plotting

    % Initialise blank mat
    combined_name_label = [];
    ratio_of_difs = [];

    % Take dif and faster order and make a string, put into matrix
    for df = 1:size(dif_mat,2)

        % Create label
        if dif_mat(2,df) == 1
            % Comparison was faster
            this_str = sprintf( '%s/30', num2str(dif_mat(1,df)) );
            this_ratio = dif_mat(1,df)/30;
        else
            % Standard was faster
            this_str = sprintf( '30/%s', num2str(dif_mat(1,df)) );
            this_ratio = 30/dif_mat(1,df);
        end

        % Add to matrix
        combined_name_label{1,df} = this_str;
        ratio_of_difs(1,df) = this_ratio;
        clear this_str this_ratio
    end
    clear df

    % Logging the ratio so the spacing is more even between values and ratio is even either side of 0
    ratio_of_difs_log = log(ratio_of_difs);

    % Add ratio into dif_mat
    dif_mat(3,:) = ratio_of_difs_log; % use log to get better spacing
    % dif_mat(3,:) = ratio_of_difs; % don't use
    clear ratio_of_difs ratio_of_difs_log


    %% Run loop to extract
    
    % Get current finger identity (if relevant)
    if dets.output_by_fing == 1
        if sr < 5
            fing_extract = num2str(sr);
        else
            fing_extract = ['1', '2', '3', '4'];
        end
    else
        fing_extract = ['1', '2', '3', '4'];
    end

    % ds = 1;
    for ds = 1:ds_loops

        % Get current difficulty
        dif_score = dif_mat(1,ds);

        % Get current faster order
        faster_order = dif_mat(2,ds);

        % Index of this combo of difficulty and faster order in dif_mat?
        i1 = find(dif_mat(1,:)==dif_score);
        i2 = find(dif_mat(2,:)==faster_order);
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
            
            % Does the finger extract identity match the one for this loop?
            if contains( fing_extract, num2str(trial_mat(ts, row_tactor)) )
                add = 1;
            else
                add = 0;
            end
            
            % Does the duration of this trial match the duration being counted for this loop?
            if round(trial_mat(ts,row_dif),2) == round(dif_score,2)
                % Leave as above
            else
                add = 0;
            end

            % ONLY for TESTING: Is the order (standard/comparison) the right one for this loop?
            if testtrainQ == 1
                if trial_mat(ts, row_faster) == faster_order
                    % Leave as above
                else
                    add = 0;
                end
            else
            end

            % If conditions are right to add (1 condition if training, 2 if testing - determined above)
            if add == 1
                % Add to counter
                cs = cs + 1;

                % Add corr data
                data(cs,1) = trial_mat(ts,row_cor); % corr/not in 1/0 format

                % Get prop "first was faster" data
                prop_faster = trial_mat(ts,row_resp);

                % Recode so is 1/0 not 1/2
                if prop_faster == 2
                    prop_faster = 0;
                else
                end

                % Add into matrix for summing below
                data(cs,2) = prop_faster;
                clear prop_faster
            else
            end

            clear add

        end
        
        % Add to dif_mat
        dif_mat(4,i) = cs;
        dif_mat(5,i) = sum(data(:,1)); % number correct
        dif_mat(6,i) = dif_mat(5,i)/dif_mat(4,i); % prop corr
        dif_mat(7,i) = sum(data(:,2)); % number first faster
        dif_mat(8,i) = dif_mat(7,i)/dif_mat(4,i); % prop faster

        clear ts cs dif_score faster_order i data

    % end ds loop
    end
    
    clear fing_extract
    clear ds_loops ds
    
    % Add all dif_mat to a big dif_mats var
    dif_mats{sr} = dif_mat;
    clear dif_mat

end

clear sr

