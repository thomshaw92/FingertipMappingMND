

% % Pasted from s3_fit_sub_logit_reg script in Columns II/ curve fitting directory


%% Fit a logestic regression model
% GLM that uses model appropriate for binomial distribution (first/second (was faster) responses)
% Also uses a logistic link that limits the predicted proportions to the actual range (0-1 proportion)

% For logistic regression, we specify the predictor matrix,
% and a matrix with one column containing the failure counts,
% and one column containing the number tested.
% We also specify the binomial distribution and the logit link.


% Get coefficients for curve (and stats, but not using them now so clear)
% [params, ~, stats] = glmfit(dataStims', [dataResp' dataCount'], 'binomial', 'logit');
[params, ~, ~] = glmfit(dataStims', [dataResp' dataCount'], 'binomial', 'logit');

% Fit to extended stimulus range to get smooth curve
curve(sr2,:) = glmval(params, dataStims_long', 'logit'); % longer dataStims makes it smoother (below)

% Fit a curve for the parameters calculated above (within stimulus range) - used for calculating R2 later
curve_range(sr2,:) = glmval(params, dataStims', 'logit')'; % using smaller set of data stims makes a clunky line with edges, but this is useful for getting R2 below

