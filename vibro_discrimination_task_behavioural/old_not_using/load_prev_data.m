
%% Load data file names in this directory - get the right ones out

% Change to Data subdir
cd(datadir)
% cd ./Data

% get names and take out of cell format
filedata = dir;
filedatacell = struct2cell(filedata);
namescell = filedatacell(1,:);
clear filedata filedatacell

ln = 0;
% Get files for this participant
for l = 1:length(namescell)
    name = namescell{l};
    
    % see if filename has participant name in it
    if contains(name, subcode) == 1
        
        ln = ln+1;
        % add to list for all real non index files
        name = cellstr(name);
        subnames(ln,:) = name;
        
    end
end
clear l ln name namescell


% Work out what file name you want depending on what session it is - if train 1 take from testing, otherwise take from previous training
if testtrainQ == 2
    if train_no == 1
        name_find = 'test1';
        dif_levels_all_level = 4;
    elseif train_no == 2
        name_find = 'train1';
        dif_levels_all_level = 5;
    elseif train_no == 3
        name_find = 'train2';
        dif_levels_all_level = 6;
    elseif train_no == 4
        name_find = 'train3';
        dif_levels_all_level = 7;
    else
    end
else
    name_find = 'test1';
    dif_levels_all_level = 1;
end


% Load file with qualifier 'name_find' in it
for l = 1:length(subnames)
    name = subnames{l};
    
    % Check its got the string in it we specified above
    if contains(name, name_find) == 1
        % Isn't a practice file
        if contains(name, 'practice') == 0
            % Isn't an image
            if contains(name, '.bmp') == 0
                datafile = load(name);
            end
        end
    end
end
clear l name subnames


% Get things to present on screen for checking
if testtrainQ == 2
    if train_no == 1
        % Get thresh name
        thresh_find = [(name_find) '_coords'];
        
        % Work out if previous test split by fingers or not (it should have been) - append tactor 1 to thresh find name if so
        if datafile.dets.output_by_fing == 1
            thresh_find = [thresh_find, '_num', num2str(fing)];

            if fing == 1
                thresh_find = [thresh_find, '_left_middle'];
            else
            end
        else
        end
        
        thresh_from_prev_sess = datafile.thresh.(thresh_find);
        thresh_from_prev_sess = thresh_from_prev_sess(2);
        clear thresh_find name_find

        % Get difficulty level closest to that threshold
        closest_dif_level_from_prev_sess = datafile.thresh.closest_dif_to_thresh;
    else
        % Grab previous training levels
        dif_levels_last = datafile.dif_levels_all{dif_levels_all_level-1};

        % Grab change value
        change_last = datafile.train_change;
    end
else
end

% Extract levels for training - calc'd last time
dif_levels = datafile.dif_levels_all{dif_levels_all_level};

% Extract dif_levels_all from last testing (not re-calc'ing after first test)
dif_levels_all = datafile.dif_levels_all;

clear datafile dif_levels_all_level

% Change dir back up three
cd ../../..

