
% Fit Weibull copied from s3_fit_weibulls in Columns II/ Curve fitting folder on 050522
% Thresh and R2 copied from s4_extra_things on same day


%% Fit Weibull (Vanessa version)

% Define function and start values that will be used to fit data
%four free parameters:
%f = @(F,x) F(3) + (1 - F(3) - F(4)).*(1 - exp(-1*(x./F(1)).^F(2))); %four free parameters
%startvalues=[1 1 0.5 0.02]; %define start values alpha, beta, gamma, lambda

%two free parameters (gamma=0.5 and lambda=0.02)
%f = @(F,x) 0.5 + (1 - 0.5 - 0.02).*(1 - exp(-1*(x./F(1)).^F(2)));
%startvalues=[1 1]; %define start values alpha, beta

%two free parameters (gamma and lambda are set - add their values below)
gamma = 0.5; % lower bound of distribution - base rate of performance in the absence of signal (guess rate)
lambda = 0.01; % 2AFC experiments, this is the lapse rate - rate at which they perform incorrectly regardless of stimulus intensity
f = @(F,x) gamma + (1 - gamma - lambda).*(1 - exp(-1*(x./F(1)).^F(2)));
clear gamma lambda

% Define start values alpha, beta
% startvalues=[1 1]; % original ones used
startvalues=[35 35];

% Set some options for the fitting
options = statset('nlinfit');
options.RobustWgtFun = [ ];% 'bisquare';

% calc fit parameters, params (parameters alpha & beta - the free parameters that needed calculating) and what I think might be the residuals, r (difference of each point from the curve)
% [params, r] = nlinfit(dataStims,dataProp,f,startvalues,options,'Weights',dataCount); % not using r
[params, ~] = nlinfit(dataStims,dataProp,f,startvalues,options,'Weights',dataCount);
clear options startvalues

% Calculate values of the curve - using the extended range of stimulus values, dataStims_long (so you get a smooth curve)
curve(sr2,:) = f(params, dataStims_long);

% Calc curve that is not smooth - using restricted stimulus range
curve_range(sr2,:) = f(params, dataStims);

clear ans

