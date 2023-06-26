

% Generate counter-balanced list of body conditions for each participant

% Conditions
cond_names = ["LEFT HAND"; ...
            "RIGHT HAND"; ...
            "LEFT ELBOW"; ...
            "RIGHT ELBOW"; ...
            "LEFT FOOT"; ...
            "RIGHT FOOT"; ...
            "LIPS"];


%% Set up

% Enter number of conditions
conds = 1:7;

% Generate all combinatons of 1-7
all_orders = flip(perms(conds),1);
clear conds

% Randomly re-order
all_orders_rand = all_orders(randperm(size(all_orders, 1)), :);
clear all_orders


%% Save

save('BodyLoc_all_order.mat');

