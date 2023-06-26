
%% See how performance went in this training & adjust training levels if needed

% Use perc accuracy to check performance and determine change
if mean(perc_cor_block) < 40
    % Make training 2 levels easier
    train_change = 2;
elseif mean(perc_cor_block) >= 40 && mean(perc_cor_block) < 60
    % Make training 1 easier
    train_change = 1;
elseif mean(perc_cor_block) >= 60 && mean(perc_cor_block) < 80
    % Do nothing/ use same levels
    train_change = 0;
elseif mean(perc_cor_block) >= 80
    % Make training 1 harder
    train_change = -1;
else
end

% Extract training dif levels
dif_levels_train = dif_levels_all{2};

% Get index of first training level value in dif_levels_all for training
it = find(dif_levels_train == dif_levels(1));

% Apply change to train_level start index
it = it + train_change;

% IF possible, get 4 dif_levels from train dif levels from above train level start index
% Note: dont need to include change in these if/elses as you already did the change above
if it < 1
    % Person was at bottom of training level range already (too good) - can't take them lower, use bottom 4
    dif_levels_recal = dif_levels_train(1,1:4);
    
    % Create warning
    WARN.(sprintf('train%d_get_train_levels',train_no)) = sprintf('Tried to lower train levels (harder) in training %d by %d but was too near bottom of range', train_no, train_change);
    
elseif ( it >= size(dif_levels_train,2)-2 )
    % Person is too close to the top - take the top ones
    dif_levels_recal = dif_levels_train(end-3:end);
    
    % Create warning
    WARN.(sprintf('train%d_get_train_levels',train_no)) = sprintf('Tried to increase train levels (easier) in training %d by %d but was too near top of range', train_no, train_change);
else  
    % Person has room to move - grab values 4 above start index
    dif_levels_recal = dif_levels_train(1,it:it+3);
end

clear dif_levels_train it

% Work out what level to add this training into
if train_no == 1
    add_levels = 5;
elseif train_no == 2
    add_levels = 6;
elseif train_no == 3
    add_levels = 7;
else
end

% Add it in
dif_levels_all{add_levels} = dif_levels_recal;
clear dif_levels_recal add_levels

