
% Copied (with some things removed) from plot_thresh_R2 script in Learning layers dir on 250522


%% Plot curve

if dets.figs == 1
    hold on
    if curve_fit_error == 0
        li = plot(dataStims_long, curve, 'r');
        li.LineWidth = 2;
    else
        plot(dataStims, curve, 'r:.');
    end
    % li2 = plot(dataStims, curve_range, 'r-'); % if you want to have a look at the fit with the limited number of points
    clear li li2
else
end


%% Calc threshold

% find value closest to thresh
[~, i] = min(abs(curve-thresh.value));

% This is a hack to get closest thresh within stimulus range, but might not be appropriate
% If i = 1 add one point so later things work
if i == 1
    i = i+1;
    WARN.thresh = 'Could not get a threshold within the range of accuracy (plot thresh R2)';
    
    % Add warning to plot
    text(7.5, .25, WARN.thresh,'FontSize',14, 'HorizontalAlignment', 'right')
else
end

% Add vals to thresh var
if curve_fit_error == 0
    thresh.coords = [curve(i) dataStims_long(i)];
else
    thresh.coords = [curve(i) dataStims(i)];
end


% Plot threshold
if dets.figs == 1
    plot(thresh.coords(2), thresh.coords(1), 'ko', 'MarkerFaceColor', 'k');
    
    % Add extra lines so can see threshold coords
    plot([dataStims(1) dataStims(end)],[thresh.coords(1) thresh.coords(1)], 'k:');
    plot([thresh.coords(2) thresh.coords(2)],[0 1], 'k:');
else
end

%% Calc R2

R2 = 1 - sum((dataProp - curve_range).^2)/sum((dataProp - mean(dataProp)).^2);


%% Calc slope and add to plot
% Added 070722

x = dataStims_long'; y = curve';
index = [i-1, i+1]; % the points where you want to get the slope (either side of thresh)
slope_line_coeff = polyfit(x(index), y(index), 1);
slope_line = polyval(slope_line_coeff,x);
plot(x, slope_line, 'k--');
clear x y index i


%% Plot text

if dets.figs == 1
    % Get message
    if curve_fit_error == 0
        txt = sprintf('thresh @ %.2f = %.3f, slope = %.2f, R2 = %.2f', thresh.value, thresh.coords(2), slope_line_coeff(1), R2);
        % txt = sprintf('thresh @ %.2f = %.3f, R2 = %.2f', thresh.value, thresh.coords(2), R2);
    else
        txt = sprintf('ERROR IN FITTING, interp (poor) thresh @ %.2f = %.3f, slope = %.2f, R2 = %.2f', thresh.value, thresh.coords(2), slope_line_coeff(2), R2);
        % txt = sprintf('ERROR IN FITTING, interp (poor) thresh @ %.2f = %.3f, R2 = %.2f', thresh.value, thresh.coords(2), R2);
    end
    
    % Add to plot - at certain coords specified below
    text(7.5, .05, txt,'FontSize',12, 'HorizontalAlignment', 'right')
    clear txt
    
    
    % add important details to title
    if curve_fit_error == 0
        titletext = sprintf('%s - Spatial task - %s hand %s finger - Logit reg fit', sub, hand_name, fing_name);
    else
        titletext = sprintf('%s - Spatial task - %s hand %s finger - FAILED fit', sub, hand_name, fing_name);
    end
    
    % Add title
    title(titletext);
    
    clear ans titletext
else
end
