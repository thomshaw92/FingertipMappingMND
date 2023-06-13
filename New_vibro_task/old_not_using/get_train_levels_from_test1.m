
%% Translate ratio into a difference level

% Parent script has been checked by HDJ on 01/07/22 to ensure that if you put the tactors in the order specified at the start (this order varies by participant number)
% curr_fing = 1 plays on left middle (in foam position LCR)
% curr_fing = 2 plays on left index (in foam position LR)
% curr_fing = 3 plays on right index (in foam position RL)
% curr_fing = 4 plays on right middle (in foam position RCL)

% sr/sr2 is equivalent to curr_fing - for below

% 07/07/22 - SCRIPT SET UP TO GET THRESH/ TRAIN LEVELS FOR CURR FING = 1 = LEFT MIDDLE

% Set default of whether to run this program or not - run if we aren't splitting by finger
% also run if we are splitting it by finger, but this is the trained finger run (index finger, finger1/hand1/tactor1)
get_train = 0; % 0 = don't run below/ don't get training levels

% Only run for left index finger (trained finger) - tactor 1
if dets.output_by_fing == 0
    % When collapsing over finger
    get_train = 1;
elseif dets.output_by_fing == 1 && sr2 == 1
    % When splitting by finger, and tactor is 1 (left index)
    get_train = 1;
else
end


% Run if the above conditions are satisfied
if get_train == 1
    
    % If ratio is NOT positive there is an issue - flag it (should be above 0 or there is something weird with the participant's performance)
    if thresh.(test_name)(2) < 0
        % Create a warning if condition is not met
        WARN.get_train_levels_test1 = 'ISSUE WITH THRESHOLD, COULD NOT GET SENSIBLE TRAINING LEVEL VALUES OUT OF THIS, ARTIFICIAL LOWER LIMIT USED, PLEASE REVIEW DATA';
        
        % Artificially set threshold to use to lowest positive value
        thresh_for_train_levs = 0.01;
    else
        % Everything is fine - change nothing, just make new variable out of threshold
        thresh_for_train_levs = thresh.(test_name)(2);
    end

    % Find closest ratio value (ratio index) to threshold (also in ratio)
    [~, ri] = min(abs( dif_mat(3,:)-thresh_for_train_levs ));

    % Get the corresponding diff value
    closest_diff_to_thresh = dif_mat(1,ri);
    clear ri

    % Get dif levels train into variable (as structs are annoying)
    dif_levels_train = dif_levels_all{2};

    % Find index of closest difference level to that stimulus value in the range of training dif_levels (train index)
    [~, ti] = min(abs(dif_levels_train - closest_diff_to_thresh));

    % Get the actual training diff value from training index
    trainval = dif_levels_train(1,ti);


    %% Get indices for values above and below based on whether i2 is above/below threshold

    % Initialise empty matrix for indices
    i_s = [];

    % Not ideal: if too close to bottom or top - fill with whatever appropriate
    if ti == 1
        % Too close to bottom of range - grab bottom 4 of range
        i_s = [1 2 3 4];
    elseif ti == 2 && trainval > closest_diff_to_thresh
        % As above
        i_s = [1 2 3 4];
    elseif ti == size(dif_levels_train,2)
        % Too close to top of range - get top 4 of range
        i_s = [size(dif_levels_train,2)-3 size(dif_levels_train,2)-2 size(dif_levels_train,2)-1 size(dif_levels_train,2)];
    elseif ti == size(dif_levels_train,2)-1 && trainval < closest_diff_to_thresh
        % As above
        i_s = [size(dif_levels_train,2)-3 size(dif_levels_train,2)-2 size(dif_levels_train,2)-1 size(dif_levels_train,2)];
    end


    % Ideal - fill with 2 up/ 2 down
    if isempty(i_s)
        if trainval < closest_diff_to_thresh
            i_s = [ti-1 ti ti+1 ti+2];
        else
            i_s = [ti-2 ti-1 ti ti+1];
        end
    else
    end

    % Get dif levels for training
    dif_levels_all{4} = dif_levels_train(1,i_s);
    clear ans dif_levels_train trainval
    clear i i_s ti

    % Save closest dif to thresh into thresh var
    thresh.closest_dif_to_thresh = closest_diff_to_thresh;
    clear closest_diff_to_thresh

% end of get_train is 1
else
end

clear get_train

