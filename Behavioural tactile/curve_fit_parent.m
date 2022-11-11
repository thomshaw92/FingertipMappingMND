
% Copied largely from VibroLearn_170522 on 240522


%% Get vars needed - calling them the same as in orig scripts for continuity

dataStims = dif_mat(8,:); % xaxis is sort of stim values, where down conditions get an artificial negative (not ideal, but not sure better option)
% dataStims = 1:size(dif_mat,2); % if using 1:8 matrix as x axis (problematic as gives threshold in these units which make no sense for our stimulus values)
dataProp = dif_mat(7,:); % Prop faster
% dataProp = dif_mat(5,:); % Prop corr - don't use (used by Weibull)
dataResp = dif_mat(6,:); % Count faster
dataCount = dif_mat(3,:); % Count trials

% Create extended version of dataStims (more values) so can fit a smooth curve
dataStims_long = linspace(dataStims(1), dataStims(end), 1000);

% Initialise empty var for params (then if not filled we know of curve fitting issue)
params = [];

% Set curve fit error to 0 - changes below if needed
curve_fit_error = 0;


%% Fit function - logistic regression

fit_logit_reg
fit_name = 'logit reg';


%% If curve fitting works, do next step, otherwise do back up        
if isempty(params)
    
    % Change var & make warning
    curve_fit_error = 1;
    WARN.curve_fitting = 'Params empty - curve fitting did not work';
    fit_name = 'fit failed';

    % Interpolating between data points
    curve = interp1(dataProp, 1:8);
    curve_range = curve;
else
end


%% Curve fitting worked: Plot and calc extra wanted things and add to figure

plot_thresh_R2

clear dataStims dataStims_long dataProp dataCount dataResp


%% Save image

if dets.saveoutput == 1
    
    if dets.figs == 1
        % Generate name to save figure
        titlef = sprintf([num2str(datetag), ' - Participant ', sub, ' ', hand_name, ' hand ', fing_name, ' finger - ', fit_name, ' fit']);
    
        % Add practice where relevant and .bmp
        if maintrialsQ == 0
            titlef = [titlef ' practice.bmp'];
        else
            titlef = [titlef '.bmp'];
        end
    
        % Save image
        saveas(gcf, [pwd, '/Data/', (titlef)]);
        clear titlef
    else
    end
    
else
end

