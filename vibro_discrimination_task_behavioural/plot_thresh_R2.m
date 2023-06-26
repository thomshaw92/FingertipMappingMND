

%% Plot curve

hold on
if curve_fit_error(sr2,1) == 0
    li = plot(dataStims_long, curve(sr2,:), 'r');
    li.LineWidth = 2;
else
    plot(dataStims, curve(sr2,:), 'r:.');
end
% li2 = plot(dataStims, curve_range, 'r-'); % if you want to have a look at the fit with the limited number of points
clear li li2


%% Calc threshold

% find value closest to .82
[~, i] = min(abs(curve(sr2,:)-thresh.value));

% This is a hack to get closest thresh within stimulus range, but might not be appropriate
% If i = 1 add one point so later things work
if i == 1
    i = i+1;
    WARN.thresh = 'Could not get a threshold within the range of accuracy (plot thresh R2)';
    
    % Add warning to plot
    text(-0.28, 0.85, WARN.thresh,'FontSize',14)
else
end

% Edit test name if splitting by finger
if dets.output_by_fing == 1
    % % THIS IS OLD NEED TO CHECK THIS FOR NEW TACTORS
    % get finger name - from 010722
    % curr_fing/sr/sr2 = 1 plays on left middle (in foam position LCR)
    % curr_fing/sr/sr2 = 2 plays on left index (in foam position LR)
    % curr_fing/sr/sr2 = 3 plays on right index (in foam position RL)
    % curr_fing/sr/sr2 = 4 plays on right middle (in foam position RCL)
    % sr/sr2 = 5 is all fingers (collapsed)
    if sr2 == 1
        testnameadd = 'digit1';
    elseif sr2 == 2
        testnameadd = 'digit2';
    elseif sr2 == 3
        testnameadd = 'digit3';
    elseif sr2 == 4
        testnameadd = 'digit4';
    elseif sr2 == 5
        testnameadd = 'digit5';
    else
        testnameadd = 'all_fings';
    end
else
    testnameadd = 'all_fings';
end

% Add vals to thresh var
if curve_fit_error(sr2,1) == 0
    thresh.coords = [curve(sr2,i) dataStims_long(i)];
else
    thresh.coords = [curve(sr2,i) dataStims(i)];
end

% Pull thresh for plotting reasons
this_thresh = thresh.coords;

% Plot threshold
plot(this_thresh(2), this_thresh(1), 'ko', 'MarkerFaceColor', 'k');

% Add extra lines so can see threshold coords
plot([dataStims(1) dataStims(end)],[this_thresh(1) this_thresh(1)], 'k:');
plot([this_thresh(2) this_thresh(2)],[0 1], 'k:');

% dont clear here need in later script % clear test_name


%% Calc R2

R2(sr2,1) = 1 - sum((dataProp - curve_range(sr2,:)).^2)/sum((dataProp - mean(dataProp)).^2);



%% Calc slope and add to plot
% Added 070722

x = dataStims_long'; y = curve(sr2,:)';
index = [i-1, i+1]; % the points where you want to get the slope (either side of thresh)
slope_line_coeff(sr2,:) = polyfit(x(index), y(index), 1);
slope_line(sr2,:) = polyval(slope_line_coeff(sr2,:),x);
plot(x, slope_line(sr2,:), 'k--');
clear x y index i


%% Plot text

% Get message
if curve_fit_error(sr2,1) == 0
    txt = sprintf('thresh @ %.2f = %.3f, slope = %.2f, R2 = %.2f', thresh.value, this_thresh(2), slope_line_coeff(sr2,1), R2(sr2,1));
    % no slope % txt = sprintf('thresh @ %.2f = %.3f, R2 = %.2f', thresh.value, this_thresh(2), R2(sr2,1));
else
    txt = sprintf('ERROR IN FITTING, interp (poor) thresh @ %.2f = %.3f, slope = %.2f, R2 = %.2f', thresh.value, this_thresh(2), slope_line_coeff(sr2,1), R2(sr2,1));
    % no slope % txt = sprintf('ERROR IN FITTING, interp (poor) thresh @ %.2f = %.3f, R2 = %.2f', thresh.value, this_thresh(2), R2(sr2,1));
end
clear this_thresh

% Add to plot - at certain coords specified below
text(-0.28, 0.05, txt,'FontSize',14)
clear txt

% add subject number and init
if curve_fit_error(sr2,1) == 0
    if dets.fit_type == 1
        titletext = sprintf('%s - Learn test - Logit reg fit', subcode);
    elseif dets.fit_type == 2
        titletext = sprintf('%s - Learn test - Weibull fit', subcode);
    else
    end
else
    titletext = sprintf('%s - Learn test - FAILED fit', sub);
end

% Add finger identity to title where relevant
if dets.output_by_fing == 1
    titletext = [titletext, ' - ', testnameadd];
else
end

% Add title
title(titletext, 'Interpreter', 'none');

clear ans titletext

